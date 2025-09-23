import type { Candidate, RejectedCandidate } from '../types';
import JSZip, { type JSZipObject } from 'jszip';
import * as pdfjsLib from 'pdfjs-dist';

// Configure the worker source for pdf.js to enable parallel processing.
// The URL should correspond to the one specified in the importmap in index.html.
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://aistudiocdn.com/pdfjs-dist@^4.4.168/build/pdf.worker.min.mjs';

const API_KEY = import.meta.env.VITE_OPENAI_API_KEY;

if (!API_KEY) {
  throw new Error("VITE_OPENAI_API_KEY environment variable not set");
}

const MODEL = import.meta.env.VITE_OPENAI_MODEL ?? 'gpt-4o-mini';
const MAX_RPM = Number(import.meta.env.VITE_OPENAI_MAX_RPM ?? '3');
const BASE_DELAY_MS = Number(import.meta.env.VITE_OPENAI_BASE_DELAY ?? '21000');
const MAX_BACKOFF_MS = Number(import.meta.env.VITE_OPENAI_MAX_BACKOFF ?? '60000');

interface ChatGPTAnalysis {
  candidateName: string;
  githubUrl: string;
  group: string;
  isQualified: boolean;
  score: number;
  pythonProficiency: boolean;
  aiLibraryExperience: boolean;
  mlExposure: boolean;
  aiProjectEvidence: boolean;
  justification: string;
  rejectionReason: string;
}

const delay = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

class DynamicRateLimiter {
  private lastRequestTime = 0;
  private requestCount = 0;
  private windowStart = Date.now();
  private readonly windowDuration = 60000; // 1 minute window
  private readonly maxRequestsPerWindow = Math.max(1, MAX_RPM);
  private baseDelay = Math.max(1000, BASE_DELAY_MS);

  async waitForNextRequest(): Promise<void> {
    const now = Date.now();

    if (now - this.windowStart >= this.windowDuration) {
      this.requestCount = 0;
      this.windowStart = now;
    }

    if (this.requestCount >= this.maxRequestsPerWindow) {
      const waitTime = this.windowDuration - (now - this.windowStart);
      if (waitTime > 0) {
        console.log(`Rate limit reached, waiting ${Math.ceil(waitTime / 1000)}s for window reset`);
        await delay(waitTime);
        this.requestCount = 0;
        this.windowStart = Date.now();
      }
    }

    const timeSinceLastRequest = now - this.lastRequestTime;
    if (timeSinceLastRequest < this.baseDelay) {
      const waitTime = this.baseDelay - timeSinceLastRequest;
      await delay(waitTime);
    }

    this.requestCount++;
    this.lastRequestTime = Date.now();
  }

  adjustDelay(wasSuccessful: boolean, responseTime: number): void {
    if (wasSuccessful) {
      if (responseTime < 5000 && this.baseDelay > 5000) {
        this.baseDelay = Math.max(5000, this.baseDelay - 1000);
      }
    } else {
      this.baseDelay = Math.min(MAX_BACKOFF_MS, this.baseDelay + 5000);
    }
  }
}

const rateLimiter = new DynamicRateLimiter();

const extractTextFromPdf = async (pdfData: Uint8Array): Promise<string> => {
  const loadingTask = pdfjsLib.getDocument({ data: pdfData });
  const pdf = await loadingTask.promise;
  let fullText = '';
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const textContent = await page.getTextContent();
    const pageText = textContent.items.map(item => ('str' in item ? item.str : '')).join(' ');
    fullText += pageText + '\n';
  }
  return fullText;
};

const normalizeGithubUrl = (url: string): string => {
  if (!url) {
    return '';
  }
  let normalized = url.trim().replace(/\/$/, '');
  if (!normalized.startsWith('http://') && !normalized.startsWith('https://')) {
    normalized = `https://${normalized}`;
  }
  if (normalized.startsWith('http://')) {
    normalized = normalized.replace('http://', 'https://');
  }
  normalized = normalized.replace('https://www.github.com/', 'https://github.com/');
  return normalized.includes('github.com/') ? normalized : '';
};

const isValidGitHubUrl = (url: string): boolean => {
  if (!url || typeof url !== 'string') {
    return false;
  }
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:' || parsed.hostname !== 'github.com') {
      return false;
    }
    const path = parsed.pathname.replace(/^\/+|\/+$/g, '');
    if (!path) {
      return false;
    }
    const parts = path.split('/');
    const username = parts[0];
    const reserved = new Set([
      'about','account','admin','api','apps','assets','blog','business','contact','dashboard','developer','docs','enterprise',
      'explore','features','gist','help','home','join','login','logout','marketplace','new','notifications','organizations',
      'pricing','privacy','search','security','settings','site','support','team','terms','topics','trending','users','www'
    ]);
    if (!username || reserved.has(username.toLowerCase())) {
      return false;
    }
    const validChars = /^[a-zA-Z0-9-]+$/;
    if (!validChars.test(username) || username.startsWith('-') || username.endsWith('-') || username.includes('--')) {
      return false;
    }
    return true;
  } catch (error) {
    console.warn(`Error validating GitHub URL ${url}:`, error);
    return false;
  }
};

const extractGitHubLinks = (text: string): string[] => {
  const githubLinks: string[] = [];
  const textClean = text.replace(/\n/g, ' ').replace(/\t/g, ' ');

  const urlPatterns = [
    /https?:\/\/github\.com\/[a-zA-Z0-9._-]+(?:\/[a-zA-Z0-9._/-]*)?/gi,
    /https?:\/\/www\.github\.com\/[a-zA-Z0-9._-]+(?:\/[a-zA-Z0-9._/-]*)?/gi,
  ];
  urlPatterns.forEach((pattern) => {
    const matches = textClean.match(pattern) ?? [];
    githubLinks.push(...matches);
  });

  const domainPatterns = [
    /(?:www\.)?github\.com\/[a-zA-Z0-9._-]+(?:\/[a-zA-Z0-9._/-]*)?/gi,
    /(?:^|\s)github\.com\/[a-zA-Z0-9._-]+(?:\/[a-zA-Z0-9._/-]*)?(?:\s|$)/gi,
  ];
  domainPatterns.forEach((pattern) => {
    const matches = textClean.match(pattern) ?? [];
    matches.forEach((match) => {
      const cleaned = match.trim();
      if (!cleaned.startsWith('http://') && !cleaned.startsWith('https://')) {
        githubLinks.push(`https://${cleaned}`);
      } else {
        githubLinks.push(cleaned);
      }
    });
  });

  const usernamePatterns = [
    /github\s*:\s*([a-zA-Z0-9._-]+)/gi,
    /@([a-zA-Z0-9._-]+)\s*(?:\(?\s*(?:on\s+)?github\s*\)?)/gi,
    /github\s+@([a-zA-Z0-9._-]+)/gi,
    /github\s+(?:profile|account|handle)\s*:\s*([a-zA-Z0-9._-]+)/gi,
    /(?:^|\s)([a-zA-Z0-9._-]{3,})\s+on\s+github(?:\s|$)/gi,
    /github\s+(?:username|id|handle)\s*:\s*([a-zA-Z0-9._-]+)/gi,
    /(?:^|\s)git\s*:\s*([a-zA-Z0-9._-]{3,})(?:\s|$)/gi,
  ];
  usernamePatterns.forEach((pattern) => {
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(textClean)) !== null) {
      const username = match[1]?.trim();
      if (username && username.length > 2 && !['hub', 'com', 'www'].includes(username.toLowerCase())) {
        githubLinks.push(`https://github.com/${username}`);
      }
    }
  });

  const emailPattern = /([a-zA-Z0-9._-]+)@github\.com/gi;
  let emailMatch: RegExpExecArray | null;
  while ((emailMatch = emailPattern.exec(textClean)) !== null) {
    const username = emailMatch[1];
    if (username && username.length > 2) {
      githubLinks.push(`https://github.com/${username}`);
    }
  }

  const contactPatterns = [
    /[•·▪▫-]\s*github\s*[:\-]?\s*([a-zA-Z0-9._-]+)/gi,
    /(?:source\s+code|code|repository|repo)\s*:\s*(?:https?:\/\/)?(?:www\.)?github\.com\/([a-zA-Z0-9._-]+)/gi,
  ];
  contactPatterns.forEach((pattern) => {
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(textClean)) !== null) {
      const username = match[1]?.trim();
      if (username && username.length > 2 && !['hub', 'com', 'www', 'profile', 'account'].includes(username.toLowerCase())) {
        githubLinks.push(`https://github.com/${username}`);
      }
    }
  });

  const normalizedLinks: string[] = [];
  githubLinks.forEach((link) => {
    const normalized = normalizeGithubUrl(link);
    if (normalized && isValidGitHubUrl(normalized)) {
      normalizedLinks.push(normalized);
    }
  });

  const seenUsernames = new Set<string>();
  const uniqueLinks: string[] = [];

  normalizedLinks.forEach((link) => {
    try {
      const url = new URL(link);
      const segments = url.pathname.split('/').filter(Boolean);
      const username = segments[0];
      if (!username || seenUsernames.has(username)) {
        return;
      }
      if (segments.length === 1) {
        seenUsernames.add(username);
        uniqueLinks.push(link);
      }
    } catch {
      // ignore malformed URL - already validated earlier
    }
  });

  normalizedLinks.forEach((link) => {
    try {
      const url = new URL(link);
      const segments = url.pathname.split('/').filter(Boolean);
      const username = segments[0];
      if (username && !seenUsernames.has(username)) {
        seenUsernames.add(username);
        uniqueLinks.push(link);
      }
    } catch {
      // ignore malformed URL
    }
  });

  return uniqueLinks;
};

const makeChatGPTRequest = async (prompt: string, maxRetries: number = 3): Promise<ChatGPTAnalysis> => {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    const startTime = Date.now();
    try {
      await rateLimiter.waitForNextRequest();

      console.log(`Calling ChatGPT (attempt ${attempt}/${maxRetries})`);
      const httpResponse = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${API_KEY}`,
        },
        body: JSON.stringify({
          model: MODEL,
          temperature: 0.2,
          response_format: { type: 'json_object' },
          messages: [
            { role: 'system', content: 'You are an expert Talent Acquisition specialist. Return only valid JSON.' },
            { role: 'user', content: prompt },
          ],
        }),
      });

      const payload = await httpResponse.json().catch(() => null);

      if (!httpResponse.ok || !payload) {
        const errorMessage = payload?.error?.message ?? httpResponse.statusText ?? 'Unknown OpenAI error';
        const err: any = new Error(errorMessage);
        err.status = httpResponse.status;
        err.retryAfter = httpResponse.headers.get('retry-after');
        throw err;
      }

      const responseTime = Date.now() - startTime;
      rateLimiter.adjustDelay(true, responseTime);

      const choice = payload.choices?.[0];
      const messageContent = choice?.message?.content;
      let rawContent = '';
      if (Array.isArray(messageContent)) {
        rawContent = messageContent
          .map((part: any) => (typeof part === 'string' ? part : part?.text ?? ''))
          .join('');
      } else if (typeof messageContent === 'string') {
        rawContent = messageContent;
      }

      if (!rawContent.trim()) {
        throw new Error('ChatGPT response did not include content');
      }

      let cleaned = rawContent.trim();
      if (cleaned.includes('```json')) {
        cleaned = cleaned.split('```json')[1]?.split('```')[0] ?? cleaned;
      } else if (cleaned.includes('```')) {
        cleaned = cleaned.split('```')[1]?.split('```')[0] ?? cleaned;
      }

      const parsed = JSON.parse(cleaned) as ChatGPTAnalysis;
      return parsed;
    } catch (error: any) {
      const responseTime = Date.now() - startTime;
      rateLimiter.adjustDelay(false, responseTime);
      console.error(`ChatGPT request failed (attempt ${attempt}):`, error?.message ?? error);

      const status = error?.status ?? error?.response?.status;
      const message = String(error?.message ?? '').toLowerCase();
      const isRateLimit = status === 429 || message.includes('rate limit') || message.includes('quota');

      if (isRateLimit && attempt < maxRetries) {
        let delayMs = BASE_DELAY_MS * Math.pow(1.5, attempt - 1);
        const retryAfter = error?.retryAfter;
        if (retryAfter) {
          const parsedDelay = Number(retryAfter) * 1000;
          if (!Number.isNaN(parsedDelay) && parsedDelay > 0) {
            delayMs = parsedDelay;
          }
        }
        delayMs = Math.min(delayMs, MAX_BACKOFF_MS);
        console.log(`Rate limit detected, waiting ${Math.ceil(delayMs / 1000)}s before retry`);
        await delay(delayMs);
        continue;
      }

      throw error;
    }
  }

  throw new Error('Exceeded retries due to rate limiting');
};

const isValidPdfName = (file: JSZipObject): boolean => {
  if (file.dir) {
    return false;
  }
  const lowerName = file.name.toLowerCase();
  return lowerName.endsWith('.pdf') && !lowerName.startsWith('__MACOSX') && !lowerName.startsWith('._');
};

export const rankResumes = async (
  jobDescription: string,
  resumeFiles: File[],
  onProgress?: (current: number, total: number) => void
): Promise<{ ranked: Candidate[], rejected: RejectedCandidate[] }> => {
  if (resumeFiles.length === 0) {
    return { ranked: [], rejected: [] };
  }

  const zipFile = resumeFiles[0];
  const jszip = new JSZip();
  const zip = await jszip.loadAsync(zipFile);

  const pdfEntries = Object.values(zip.files).filter((file: JSZipObject) => isValidPdfName(file));
  console.log(`Pre-processing ${pdfEntries.length} PDF files...`);

  const preprocessedFiles = await Promise.all(pdfEntries.map(async (zipEntry) => {
    try {
      const pdfData = await zipEntry.async('uint8array');
      const resumeText = await extractTextFromPdf(pdfData);

      if (!resumeText.trim()) {
        throw new Error('PDF is empty or could not be read.');
      }

      const detectedGitHubLinks = extractGitHubLinks(resumeText);
      const githubLinksText = detectedGitHubLinks.length > 0
        ? `\n\n**DETECTED GITHUB LINKS:** ${detectedGitHubLinks.join(', ')}`
        : '';

      return {
        zipEntry,
        resumeText,
        githubLinksText,
        githubLinks: detectedGitHubLinks,
        error: null as Error | null,
      };
    } catch (error) {
      return {
        zipEntry,
        resumeText: '',
        githubLinksText: '',
        githubLinks: [] as string[],
        error: error as Error,
      };
    }
  }));

  console.log('Pre-processing complete. Starting AI analysis...');
  const ranked: Candidate[] = [];
  const rejected: RejectedCandidate[] = [];

  for (let i = 0; i < preprocessedFiles.length; i++) {
    const { zipEntry, resumeText, githubLinksText, githubLinks, error } = preprocessedFiles[i];
    onProgress?.(i + 1, preprocessedFiles.length);

    if (error || !resumeText.trim()) {
      rejected.push({
        id: `${zipEntry.name}-${Date.now()}`,
        name: 'Processing Error',
        reason: 'Failed to read or parse PDF file.',
        fileName: zipEntry.name,
      });
      continue;
    }

    if (githubLinks.length === 0) {
      rejected.push({
        id: `${zipEntry.name}-${Date.now()}`,
        name: 'Unknown Candidate',
        reason: 'No valid GitHub profile found.',
        fileName: zipEntry.name,
      });
      continue;
    }

    try {
      const prompt = `
You are an expert Talent Acquisition specialist analyzing resumes for AI Engineer (Intern) positions. Your task is to categorize candidates into three groups based on specific criteria.

**Job Description:**
---
${jobDescription}
---

**Candidate Resume:**
---
${resumeText}
---${githubLinksText}

**CLASSIFICATION GROUPS:**
- **Group 1: High potential (shortlist)** - Score: 80-100
- **Group 2: Silver medalist (Batch 2)** - Score: 60-79
- **Group 3: Rejected (not suitable)** - Score: 0-59

**MANDATORY CRITERIA (Automatic rejection if not met):**
1. **GitHub link is mandatory** - Absence leads to automatic Group 3 rejection

**GITHUB LINK DETECTION INSTRUCTIONS:**
- Look for GitHub URLs in various formats: https://github.com/username, github.com/username
- Check for embedded references like "GitHub: username", "@username on GitHub", or "github.com/username"
- Accept GitHub profile links, repository links, or any valid GitHub URL
- If multiple GitHub links are found, use the most appropriate profile URL
- Convert incomplete GitHub references to full URLs (e.g., "github.com/user" → "https://github.com/user")

**PRIMARY EVALUATION CRITERIA:**
2. **Strong Python proficiency** - Demonstrated through resume projects
3. **AI Library experience** - TensorFlow, PyTorch, NumPy, Pandas, Scikit-learn, Matplotlib, etc.
4. **ML Model exposure** - Especially LLMs. Neural Networks or Diffusion models are bonus points
5. **AI Fundamentals understanding** - Generative AI, Machine Learning, Deep Learning
6. **AI Project evidence** - Projects that validate AI domain proficiency

**CLASSIFICATION LOGIC:**
- **Group 3**: No GitHub link OR lacks basic Python/AI requirements
- **Group 2**: Has GitHub + meets 3-4 primary criteria with decent AI exposure
- **Group 1**: Has GitHub + meets 5-6 primary criteria with strong AI project evidence

**INSTRUCTIONS:**
1. Thoroughly search for GitHub links in ALL formats (URLs, embedded references, usernames)
2. If any GitHub reference is found, extract and format it as a complete URL
3. Evaluate each primary criteria (pythonProficiency, aiLibraryExperience, mlExposure, aiProjectEvidence)
4. Assign appropriate group based on criteria met
5. Provide detailed justification explaining the classification and GitHub link detection
6. Extract candidate name or use 'Unknown Candidate'

Return your analysis in the following JSON format:
{
    "candidateName": "string",
    "githubUrl": "string",
    "group": "string",
    "isQualified": boolean,
    "score": integer,
    "pythonProficiency": boolean,
    "aiLibraryExperience": boolean,
    "mlExposure": boolean,
    "aiProjectEvidence": boolean,
    "justification": "string",
    "rejectionReason": "string"
}
`;

      console.log(`Processing resume: ${zipEntry.name}`);
      const resultJson = await makeChatGPTRequest(prompt);

      const id = `${zipEntry.name}-${Date.now()}`;
      const isUrlValid = isValidGitHubUrl(resultJson.githubUrl);

      if (resultJson.isQualified && isUrlValid &&
        (resultJson.group === 'Group 1: High potential' || resultJson.group === 'Group 2: Silver medalist')) {
        ranked.push({
          id,
          name: resultJson.candidateName,
          githubUrl: resultJson.githubUrl,
          group: resultJson.group,
          score: resultJson.score,
          pythonProficiency: resultJson.pythonProficiency,
          aiLibraryExperience: resultJson.aiLibraryExperience,
          mlExposure: resultJson.mlExposure,
          aiProjectEvidence: resultJson.aiProjectEvidence,
          justification: resultJson.justification,
          fileName: zipEntry.name,
        });
      } else {
        let reason = resultJson.rejectionReason;
        if (resultJson.isQualified && !isUrlValid) {
          reason = 'Invalid or malformed GitHub URL found.';
        } else if (!reason) {
          reason = 'No valid GitHub profile found.';
        }
        rejected.push({
          id,
          name: resultJson.candidateName,
          reason,
          fileName: zipEntry.name,
        });
      }
    } catch (error) {
      console.error(`Failed to process file ${zipEntry.name}:`, error);
      rejected.push({
        id: `${zipEntry.name}-${Date.now()}`,
        name: 'Processing Error',
        reason: 'Failed to read or parse PDF file.',
        fileName: zipEntry.name,
      });
    }
  }

  ranked.sort((a, b) => b.score - a.score);
  return { ranked, rejected };
};

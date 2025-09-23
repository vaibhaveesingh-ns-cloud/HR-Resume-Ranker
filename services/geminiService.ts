import { GoogleGenAI, Type } from "@google/genai";
import type { Candidate, RejectedCandidate } from '../types';
// FIX: Import JSZipObject type to correctly type the zip file entries.
import JSZip, { type JSZipObject } from 'jszip';
import * as pdfjsLib from 'pdfjs-dist';

// Configure the worker source for pdf.js to enable parallel processing.
// The URL should correspond to the one specified in the importmap in index.html.
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://aistudiocdn.com/pdfjs-dist@^4.4.168/build/pdf.worker.min.mjs';


// Prefer Vite-style env first, then fall back to process.env definitions injected by Vite define
const API_KEY = (import.meta as any).env?.VITE_GEMINI_API_KEY || (process as any).env?.GEMINI_API_KEY || (process as any).env?.API_KEY;

if (!API_KEY) {
  throw new Error("API_KEY environment variable not set. Define VITE_GEMINI_API_KEY (preferred) or GEMINI_API_KEY/API_KEY in your .env, then restart Vite.");
}

const ai = new GoogleGenAI({ apiKey: API_KEY });

const responseSchema = {
  type: Type.OBJECT,
  properties: {
    candidateName: {
      type: Type.STRING,
      description: "The full name of the candidate.",
    },
    githubUrl: {
      type: Type.STRING,
      description: "The full URL to the candidate's GitHub profile. Should be an empty string if not found.",
    },
    group: {
      type: Type.STRING,
      description: "Classification group: 'Group 1: High potential', 'Group 2: Silver medalist', or 'Group 3: Rejected'.",
    },
    isQualified: {
      type: Type.BOOLEAN,
      description: "True if candidate meets basic requirements and has GitHub profile, false otherwise.",
    },
    score: {
      type: Type.INTEGER,
      description: "A score from 0 to 100. Group 1: 80-100, Group 2: 60-79, Group 3: 0-59.",
    },
    pythonProficiency: {
      type: Type.BOOLEAN,
      description: "True if candidate demonstrates strong Python skills through projects.",
    },
    aiLibraryExperience: {
      type: Type.BOOLEAN,
      description: "True if candidate has experience with AI libraries (TensorFlow, PyTorch, NumPy, Pandas, etc.).",
    },
    mlExposure: {
      type: Type.BOOLEAN,
      description: "True if candidate has exposure to ML models, especially LLMs, Neural Networks, or Deep Learning.",
    },
    aiProjectEvidence: {
      type: Type.BOOLEAN,
      description: "True if candidate has evidence of AI domain projects.",
    },
    justification: {
      type: Type.STRING,
      description: "Detailed explanation of the group classification and scoring based on AI Engineer criteria.",
    },
    rejectionReason: {
      type: Type.STRING,
      description: "Specific reason for rejection if in Group 3. Should be empty for Groups 1 and 2.",
    },
  },
  required: ["candidateName", "githubUrl", "group", "isQualified", "score", "pythonProficiency", "aiLibraryExperience", "mlExposure", "aiProjectEvidence", "justification", "rejectionReason"],
};

/**
 * Extracts text content from a PDF file represented as a Uint8Array.
 * @param pdfData The raw data of the PDF file.
 * @returns A promise that resolves to the extracted text content as a string.
 */
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

/**
 * Extracts GitHub links from resume text using multiple detection methods.
 * @param text The resume text to search for GitHub links.
 * @returns An array of potential GitHub URLs found in the text.
 */
const extractGitHubLinks = (text: string): string[] => {
  const githubLinks: string[] = [];
  
  // Pattern 1: Full HTTPS URLs
  const httpsPattern = /https:\/\/github\.com\/[a-zA-Z0-9._-]+(?:\/[a-zA-Z0-9._-]+)?/gi;
  const httpsMatches = text.match(httpsPattern) || [];
  githubLinks.push(...httpsMatches);
  
  // Pattern 2: github.com without protocol
  const domainPattern = /github\.com\/[a-zA-Z0-9._-]+(?:\/[a-zA-Z0-9._-]+)?/gi;
  const domainMatches = text.match(domainPattern) || [];
  domainMatches.forEach(match => {
    if (!match.startsWith('https://')) {
      githubLinks.push(`https://${match}`);
    }
  });
  
  // Pattern 3: GitHub username patterns (github: username or @username on GitHub)
  const usernamePattern = /(?:github:\s*|@)([a-zA-Z0-9._-]+)(?:\s+(?:on\s+)?github)?/gi;
  let usernameMatch;
  while ((usernameMatch = usernamePattern.exec(text)) !== null) {
    const username = usernameMatch[1];
    if (username && username.length > 2) {
      githubLinks.push(`https://github.com/${username}`);
    }
  }
  
  // Remove duplicates and return unique links
  return [...new Set(githubLinks)];
};

/**
 * Delays execution for a specified number of milliseconds.
 * @param ms The number of milliseconds to delay.
 * @returns A promise that resolves after the delay.
 */
const delay = (ms: number): Promise<void> => {
  return new Promise(resolve => setTimeout(resolve, ms));
};

/**
 * Dynamic rate limiter that adjusts delays based on API performance
 */
class DynamicRateLimiter {
  private lastRequestTime = 0;
  private requestCount = 0;
  private windowStart = Date.now();
  private readonly windowDuration = 60000; // 1 minute window
  private readonly maxRequestsPerWindow = 8; // Conservative limit for free tier
  private baseDelay = 3000; // Start with 3 seconds
  
  async waitForNextRequest(): Promise<void> {
    const now = Date.now();
    
    // Reset window if needed
    if (now - this.windowStart >= this.windowDuration) {
      this.requestCount = 0;
      this.windowStart = now;
    }
    
    // If we're at the limit, wait for the window to reset
    if (this.requestCount >= this.maxRequestsPerWindow) {
      const waitTime = this.windowDuration - (now - this.windowStart);
      if (waitTime > 0) {
        console.log(`Rate limit reached, waiting ${Math.ceil(waitTime/1000)}s for window reset`);
        await delay(waitTime);
        this.requestCount = 0;
        this.windowStart = Date.now();
      }
    }
    
    // Ensure minimum delay between requests
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
      // Gradually reduce delay if requests are successful and fast
      if (responseTime < 2000 && this.baseDelay > 2000) {
        this.baseDelay = Math.max(2000, this.baseDelay - 200);
      }
    } else {
      // Increase delay if request failed
      this.baseDelay = Math.min(8000, this.baseDelay + 1000);
    }
  }
}

// Global rate limiter instance
const rateLimiter = new DynamicRateLimiter();

/**
 * Makes a request to Gemini API with intelligent rate limiting and retry logic.
 * @param prompt The prompt to send to the API.
 * @param maxRetries Maximum number of retry attempts.
 * @returns The API response.
 */
const makeGeminiRequest = async (prompt: string, maxRetries: number = 3): Promise<any> => {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    const startTime = Date.now();
    
    try {
      // Wait for rate limiter before making request
      await rateLimiter.waitForNextRequest();
      
      console.log(`Making API request (attempt ${attempt}/${maxRetries})`);
      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: prompt,
        config: {
          responseMimeType: "application/json",
          responseSchema: responseSchema,
        },
      });
      
      const responseTime = Date.now() - startTime;
      rateLimiter.adjustDelay(true, responseTime);
      console.log(`API request successful (${responseTime}ms)`);
      return response;
      
    } catch (error: any) {
      const responseTime = Date.now() - startTime;
      rateLimiter.adjustDelay(false, responseTime);
      console.error(`API request failed (attempt ${attempt}):`, error?.message || error);
      
      // Check for rate limit errors
      const isRateLimit = error?.status === 'RESOURCE_EXHAUSTED' || 
                         error?.message?.includes('429') || 
                         error?.message?.includes('quota') ||
                         error?.message?.includes('rate limit');
      
      if (isRateLimit && attempt < maxRetries) {
        // Extract retry delay from error or use exponential backoff
        const retryDelay = error?.details?.find((d: any) => d['@type']?.includes('RetryInfo'))?.retryDelay;
        let delayMs;
        
        if (retryDelay) {
          delayMs = parseInt(retryDelay.replace('s', '')) * 1000;
        } else {
          // Shorter exponential backoff: 5s, 10s, 20s
          delayMs = Math.min(5000 * Math.pow(2, attempt - 1), 30000);
        }
        
        console.log(`Rate limit detected, waiting ${delayMs/1000}s before retry`);
        await delay(delayMs);
        continue;
      }
      
      // If not a rate limit error or max retries reached, throw the error
      throw error;
    }
  }
};

/**
 * Validates if a given string is a valid and secure GitHub URL.
 * @param url The URL string to validate.
 * @returns True if the URL is a valid https://github.com URL, false otherwise.
 */
const isValidGitHubUrl = (url: string): boolean => {
  if (!url || typeof url !== 'string') {
    return false;
  }
  try {
    const parsedUrl = new URL(url);
    // Ensure it's a secure URL and the host is exactly 'github.com'.
    return parsedUrl.protocol === 'https:' && parsedUrl.hostname === 'github.com';
  } catch (e) {
    // URL parsing failed, so it's not a valid URL.
    return false;
  }
};


export const rankResumes = async (jobDescription: string, resumeFiles: File[], onProgress?: (current: number, total: number) => void): Promise<{ ranked: Candidate[], rejected: RejectedCandidate[] }> => {
  if (resumeFiles.length === 0) {
    return { ranked: [], rejected: [] };
  }
  const zipFile = resumeFiles[0]; // We expect only one zip file.

  const jszip = new JSZip();
  const zip = await jszip.loadAsync(zipFile);

  const pdfFiles = Object.values(zip.files)
    // FIX: Explicitly type `file` as JSZipObject to prevent it from being inferred as `unknown`.
    .filter((file: JSZipObject) => !file.dir && file.name.toLowerCase().endsWith('.pdf') && !file.name.startsWith('__MACOSX'));

  console.log(`Pre-processing ${pdfFiles.length} PDF files...`);
  
  // Pre-process all PDFs in parallel (this doesn't hit the API)
  const preprocessedFiles = await Promise.all(
    pdfFiles.map(async (zipEntry) => {
      try {
        const pdfData = await zipEntry.async('uint8array');
        const resumeText = await extractTextFromPdf(pdfData);
        
        if (!resumeText.trim()) {
          throw new Error('PDF is empty or could not be read.');
        }

        // Extract potential GitHub links from resume text
        const detectedGitHubLinks = extractGitHubLinks(resumeText);
        const githubLinksText = detectedGitHubLinks.length > 0 ? 
          `\n\n**DETECTED GITHUB LINKS:** ${detectedGitHubLinks.join(', ')}` : '';
        
        return {
          zipEntry,
          resumeText,
          githubLinksText,
          error: null
        };
      } catch (error) {
        return {
          zipEntry,
          resumeText: '',
          githubLinksText: '',
          error: error as Error
        };
      }
    })
  );
  
  console.log(`Pre-processing complete. Starting AI analysis...`);
  const results: any[] = [];
  
  // Process AI analysis sequentially with dynamic rate limiting
  for (let i = 0; i < preprocessedFiles.length; i++) {
    const { zipEntry, resumeText, githubLinksText, error } = preprocessedFiles[i];
    onProgress?.(i + 1, preprocessedFiles.length);
    
    if (error || !resumeText.trim()) {
      results.push({
        candidateName: 'Processing Error',
        githubUrl: '',
        group: 'Group 3: Rejected',
        isQualified: false,
        score: 0,
        pythonProficiency: false,
        aiLibraryExperience: false,
        mlExposure: false,
        aiProjectEvidence: false,
        justification: `An error occurred while analyzing this resume. It might be empty, corrupted, or password-protected.`,
        rejectionReason: 'Failed to read or parse PDF file.',
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
          7. Return analysis in the specified JSON format
        `;

        console.log(`Processing resume: ${zipEntry.name}`);
        const startTime = Date.now();
        const response = await makeGeminiRequest(prompt);
        const resultJson = JSON.parse(response.text);
        const processingTime = Date.now() - startTime;
        
        results.push({
          ...resultJson,
          fileName: zipEntry.name,
        });
        console.log(`Successfully processed: ${zipEntry.name} (${processingTime}ms)`);

      } catch (error) {
        console.error(`Failed to process file ${zipEntry.name}:`, error);
        results.push({
          candidateName: 'Processing Error',
          githubUrl: '',
          group: 'Group 3: Rejected',
          isQualified: false,
          score: 0,
          pythonProficiency: false,
          aiLibraryExperience: false,
          mlExposure: false,
          aiProjectEvidence: false,
          justification: `An error occurred while analyzing this resume. It might be empty, corrupted, or password-protected.`,
          rejectionReason: 'Failed to read or parse PDF file.',
          fileName: zipEntry.name,
        });
      }
  }

  const ranked: Candidate[] = [];
  const rejected: RejectedCandidate[] = [];

  results.forEach((res) => {
    const id = `${res.fileName}-${Date.now()}`;
    const isUrlValid = isValidGitHubUrl(res.githubUrl);

    if (res.isQualified && isUrlValid && (res.group === 'Group 1: High potential' || res.group === 'Group 2: Silver medalist')) {
      ranked.push({
        id,
        name: res.candidateName,
        githubUrl: res.githubUrl,
        group: res.group,
        score: res.score,
        pythonProficiency: res.pythonProficiency,
        aiLibraryExperience: res.aiLibraryExperience,
        mlExposure: res.mlExposure,
        aiProjectEvidence: res.aiProjectEvidence,
        justification: res.justification,
        fileName: res.fileName,
      });
    } else {
      // Determine the correct rejection reason.
      let reason = res.rejectionReason;
      if (res.isQualified && !isUrlValid) {
        // The AI thought it was qualified, but the URL was bad.
        reason = 'Invalid or malformed GitHub URL found.';
      } else if (!reason) {
        // Fallback for unexpected cases where no reason is provided.
        reason = 'No valid GitHub profile found.';
      }

      rejected.push({
        id,
        name: res.candidateName,
        reason: reason,
        fileName: res.fileName,
      });
    }
  });
  
  ranked.sort((a, b) => b.score - a.score);

  return { ranked, rejected };
};
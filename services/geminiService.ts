import { GoogleGenAI, Type } from "@google/genai";
import type { Candidate, RejectedCandidate } from '../types';
// FIX: Import JSZipObject type to correctly type the zip file entries.
import JSZip, { type JSZipObject } from 'jszip';
import * as pdfjsLib from 'pdfjs-dist';

// Configure the worker source for pdf.js to enable parallel processing.
// The URL should correspond to the one specified in the importmap in index.html.
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://aistudiocdn.com/pdfjs-dist@^4.4.168/build/pdf.worker.min.mjs';


const API_KEY = process.env.API_KEY;

if (!API_KEY) {
  throw new Error("API_KEY environment variable not set");
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
    isQualified: {
      type: Type.BOOLEAN,
      description: "True if a GitHub URL is found in the resume, false otherwise.",
    },
    score: {
      type: Type.INTEGER,
      description: "A score from 0 to 100 based on the resume's match with the job description. 0 if not qualified.",
    },
    justification: {
      type: Type.STRING,
      description: "A brief, 2-3 sentence summary explaining the score and the candidate's fit for the role.",
    },
    rejectionReason: {
      type: Type.STRING,
      description: "Reason for rejection, which must be 'No GitHub profile found.' Should be empty if qualified.",
    },
  },
  required: ["candidateName", "githubUrl", "isQualified", "score", "justification", "rejectionReason"],
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


export const rankResumes = async (jobDescription: string, resumeFiles: File[]): Promise<{ ranked: Candidate[], rejected: RejectedCandidate[] }> => {
  if (resumeFiles.length === 0) {
    return { ranked: [], rejected: [] };
  }
  const zipFile = resumeFiles[0]; // We expect only one zip file.

  const jszip = new JSZip();
  const zip = await jszip.loadAsync(zipFile);

  const analysisPromises = Object.values(zip.files)
    // FIX: Explicitly type `file` as JSZipObject to prevent it from being inferred as `unknown`.
    .filter((file: JSZipObject) => !file.dir && file.name.toLowerCase().endsWith('.pdf') && !file.name.startsWith('__MACOSX'))
    // FIX: Explicitly type `zipEntry` as JSZipObject to prevent it from being inferred as `unknown`.
    .map(async (zipEntry: JSZipObject) => {
      try {
        const pdfData = await zipEntry.async('uint8array');
        const resumeText = await extractTextFromPdf(pdfData);
        
        if (!resumeText.trim()) {
           throw new Error('PDF is empty or could not be read.');
        }

        const prompt = `
          You are an expert HR recruitment assistant. Your task is to analyze a candidate's resume against a given job description and decide if they are qualified. A GitHub profile is a mandatory requirement.

          **Job Description:**
          ---
          ${jobDescription}
          ---

          **Candidate Resume:**
          ---
          ${resumeText}
          ---

          **Instructions:**
          1.  Carefully read the resume to find a GitHub profile URL.
          2.  If **no GitHub URL is found**, the candidate is automatically rejected. Set 'isQualified' to false and 'rejectionReason' to 'No GitHub profile found.'.
          3.  If a **GitHub URL is found**, the candidate is qualified for analysis. Set 'isQualified' to true.
          4.  For qualified candidates, evaluate their skills, experience, and projects listed on the resume against the job description.
          5.  Assign a score from 0 to 100 based on how well they match the job requirements. A higher score means a better fit.
          6.  Write a concise justification for your assigned score, highlighting strengths and weaknesses.
          7.  Extract the candidate's name from the resume. If you can't find it, use 'Unknown Candidate'.
          8.  Return your analysis in the specified JSON format.
        `;

        const response = await ai.models.generateContent({
          model: 'gemini-2.5-flash',
          contents: prompt,
          config: {
            responseMimeType: "application/json",
            responseSchema: responseSchema,
          },
        });

        const resultJson = JSON.parse(response.text);

        return {
          ...resultJson,
          fileName: zipEntry.name,
        };

      } catch (error) {
        console.error(`Failed to process file ${zipEntry.name}:`, error);
        return {
          candidateName: 'Processing Error',
          githubUrl: '',
          isQualified: false,
          score: 0,
          justification: `An error occurred while analyzing this resume. It might be empty, corrupted, or password-protected.`,
          rejectionReason: 'Failed to read or parse PDF file.',
          fileName: zipEntry.name,
        };
      }
    });

  const results = await Promise.all(analysisPromises);

  const ranked: Candidate[] = [];
  const rejected: RejectedCandidate[] = [];

  results.forEach((res) => {
    const id = `${res.fileName}-${Date.now()}`;
    const isUrlValid = isValidGitHubUrl(res.githubUrl);

    if (res.isQualified && isUrlValid) {
      ranked.push({
        id,
        name: res.candidateName,
        githubUrl: res.githubUrl,
        score: res.score,
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
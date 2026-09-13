import { useMutation } from '@tanstack/react-query';
import { API_URL } from '@/src/getEnv';

type UploadPdfVariables = {
  file: File;
  fileName?: string;
};

const MAX_FILE_NAME_LENGTH = 255;

/** Resolve the S3 object name: trimmed, no path separators, always a .pdf. */
export function normalizeUploadFileName(rawName: string | undefined, fallbackName: string): string {
  const cleaned = (rawName ?? '').trim().replace(/[\\/]+/g, '-').trim();
  const base = cleaned || fallbackName.trim() || 'document.pdf';
  const withExtension = /\.pdf$/i.test(base) ? base : `${base}.pdf`;
  return withExtension.slice(0, MAX_FILE_NAME_LENGTH);
}

const uploadPdfToS3 = async ({ file, fileName }: UploadPdfVariables) => {
  const resolvedName = normalizeUploadFileName(fileName, file.name);
  const signingResponse = await fetch(
    `${API_URL}/upload/presigned-url?file_name=${encodeURIComponent(resolvedName)}`,
  );
  if (!signingResponse.ok) {
    throw new Error('Failed to get a presigned URL');
  }

  // The router returns the URL as a JSON string.
  const presignedUrl: unknown = await signingResponse.json();
  if (typeof presignedUrl !== 'string' || !presignedUrl) {
    throw new Error('Invalid presigned URL response');
  }

  const response = await fetch(presignedUrl, {
    method: 'PUT',
    body: file,
    headers: { 'Content-Type': 'application/pdf' },
  });
  if (!response.ok) {
    throw new Error('Failed to upload file to S3');
  }
  return response;
};

export const useUploadPdf = () => useMutation({ mutationFn: uploadPdfToS3 });

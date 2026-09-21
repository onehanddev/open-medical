import { API_URL } from '@/src/getEnv';

export const getRetrievalUrl = async (documentName: string) => {
  const response = await fetch(
    `${API_URL}/ask/get-retrieval-url?document_name=${encodeURIComponent(documentName)}`
  );

  if (!response.ok) {
    throw new Error("Failed to create source URL.");
  }

  return response.json();
};

export const fetchSource = async (
  baseUrl: string,
  signedQuery: string,
  pageNumber: number
) => {
  const response = await fetch(
    `${baseUrl}/page_${pageNumber}.md?${signedQuery}`
  );

  if (!response.ok) {
    throw new Error("Failed to load source page.");
  }

  return response.text();
};

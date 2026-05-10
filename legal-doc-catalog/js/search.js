import { supabase } from './supabase-client.js';

let debounceTimer = null;

export function debounceSearch(query, callback, delay = 300) {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => callback(query), delay);
}

export async function searchDocuments(query) {
  const { data, error } = await supabase
    .rpc('search_documents', { search_query: query });
  if (error) throw error;
  return data;
}

export async function fetchAllDocuments() {
  const { data, error } = await supabase
    .from('documents')
    .select('id, title, category, year, word_count')
    .order('title');
  if (error) throw error;
  return data;
}

export async function fetchDocument(id) {
  const { data, error } = await supabase
    .from('documents')
    .select('*')
    .eq('id', id)
    .single();
  if (error) throw error;
  return data;
}

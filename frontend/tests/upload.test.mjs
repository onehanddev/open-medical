import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import ts from 'typescript';
import { QueryClient } from '@tanstack/react-query';

function uploadWith(fetch) {
  const source = readFileSync(new URL('../src/components/upload/useUploadPdf.tsx', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '').replace(/^export\s+/gm, '');
  const code = ts.transpile(source, { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None });
  return vm.runInNewContext(`${code}\nuseUploadPdf().mutationFn`, {
    fetch, API_URL: 'https://api.example.test', useMutation: options => options,
    useQueryClient: () => new QueryClient(), console,
  });
}

test('requests a signed URL with the selected filename before uploading its bytes', async () => {
  const calls = [];
  const file = { name: 'Book + notes & résumé.pdf' };
  const signedUrl = 'https://storage.example.test/signed';
  const upload = uploadWith(async (url, options) => {
    calls.push({ url, options });
    return calls.length === 1 ? { ok: true, json: async () => signedUrl } : { ok: true };
  });
  await upload({ fileName: file.name, file });
  assert.equal(calls.length, 2);
  assert.equal(new URL(calls[0].url).searchParams.get('file_name'), file.name);
  assert.equal(calls[1].url, signedUrl);
  assert.equal(calls[1].options.method, 'PUT');
  assert.equal(calls[1].options.body, file);
});

test('saves the file under a user-provided name', async () => {
  const calls = [];
  const file = { name: 'scan001.pdf' };
  const upload = uploadWith(async (url, options) => {
    calls.push({ url, options });
    return calls.length === 1
      ? { ok: true, json: async () => 'https://storage.example.test/signed' }
      : { ok: true };
  });
  await upload({ file, fileName: 'Anatomy - Lower Limb' });
  assert.equal(new URL(calls[0].url).searchParams.get('file_name'), 'Anatomy - Lower Limb.pdf');
  assert.equal(calls[1].options.body, file);
});

test('falls back to the original filename when no custom name is given', async () => {
  const calls = [];
  const upload = uploadWith(async (url) => {
    calls.push(url);
    return calls.length === 1
      ? { ok: true, json: async () => 'https://storage.example.test/signed' }
      : { ok: true };
  });
  await upload({ file: { name: 'original.pdf' } });
  assert.equal(new URL(calls[0]).searchParams.get('file_name'), 'original.pdf');
});

test('does not upload when signing fails', async () => {
  let calls = 0;
  const upload = uploadWith(async () => { calls++; return { ok: false }; });
  await assert.rejects(upload({ file: { name: 'book.pdf' } }), /presigned URL/i);
  assert.equal(calls, 1);
});

test('reports S3 upload failures', async () => {
  let calls = 0;
  const upload = uploadWith(async () => ++calls === 1
    ? { ok: true, json: async () => 'https://storage.example.test/signed' }
    : { ok: false });
  await assert.rejects(upload({ file: { name: 'book.pdf' } }), /upload file to S3/);
});

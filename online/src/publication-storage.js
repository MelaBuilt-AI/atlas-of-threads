import { fail } from './publication.js';

// Existing object keys hold the original publication envelope. New keys name
// two immutable raw JSON objects, so downloads can stream exact reviewed bytes.
export async function publicationPart(env, key, part) {
  const split = key.startsWith('publications-v2/');
  const object = await env.INQUIRIES.get(split ? key + '/' + part : key);
  if (!object) fail('Publication is temporarily unavailable', 503);
  if (split) return new Response(object.body);
  const artifact = await object.json();
  return new Response(part === 'bundle' ? artifact.inquiry_json : artifact.player_json);
}

export async function deletePublication(env, key) {
  await env.INQUIRIES.delete(key.startsWith('publications-v2/')
    ? [key + '/bundle', key + '/player'] : key);
}

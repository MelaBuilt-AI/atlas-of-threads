import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { Miniflare } from 'miniflare';
import { parse } from 'lossless-json';
import { canonical, inspect, sha, MAX_BYTES } from '../src/publication.js';
import { publicationPart } from '../src/publication-storage.js';

test('canonical hashes preserve Python key ordering and exact numeric spellings', () => {
  const value = parse('{"😀":-0.0,"\ue000":1e-05,"2":9007199254740993,"10":1.0,"a":[null,true,"line\\nquote\\\""]}');
  assert.equal(canonical(value), '{"10":1.0,"2":9007199254740993,"a":[null,true,"line\\nquote\\\""],"\ue000":1e-05,"😀":-0.0}\n');
  assert.equal(canonical({ a: undefined, b: [undefined] }), '{"b":[null]}\n');
});

test('bounded HTTP inspection still verifies individual graph hashes', async () => {
  const artifact = JSON.parse(await readFile('test/fixtures/1.json', 'utf8'));
  const bundle = parse(artifact.inquiry_json);
  bundle.content.graphs[0].shared_sha256 = '0'.repeat(64);
  bundle.id = await sha(canonical(bundle.content));
  artifact.inquiry_json = canonical(bundle);
  await assert.rejects(() => inspect(artifact, { requestBounded: true }), /Graph checksum/);
});

test('split downloads stream stored bytes without decoding JSON', async () => {
  const raw = '{"value":9007199254740993,"decimal":1.0}\n';
  const env = { INQUIRIES: { async get(key) {
    assert.equal(key, 'publications-v2/example/bundle');
    return { body: new Response(raw).body, json() { throw Error('Must stream, not parse'); } };
  } } };
  assert.equal(await (await publicationPart(env, 'publications-v2/example', 'bundle')).text(), raw);
});

test('split and legacy storage preserve exact downloads, retries and complete withdrawal', async () => {
  const mf = new Miniflare({ modules: true, scriptPath: 'dist/worker.js',
    compatibilityDate: '2026-05-15', d1Databases: ['DB'], r2Buckets: ['INQUIRIES'],
    bindings: { SITE_ORIGIN: 'http://localhost:7490' } });
  try {
    const db = await mf.getD1Database('DB'), bucket = await mf.getR2Bucket('INQUIRIES');
    for (const file of (await readdir('migrations')).filter(f => f.endsWith('.sql')).sort())
      for (const sql of (await readFile('migrations/' + file, 'utf8')).split(';').map(s => s.trim()).filter(Boolean))
        await db.prepare(sql).run();
    await db.prepare("INSERT INTO owners VALUES('a','Synthetic storage','synthetic',1)").run();
    await db.prepare("INSERT INTO instances VALUES('a','a','Synthetic storage',?,1,NULL)").bind(await sha('synthetic-key')).run();
    const req = (path, data) => mf.dispatchFetch('http://localhost:7490' + path, {
      method: data === undefined ? 'GET' : 'POST',
      headers: { Authorization: 'Bearer synthetic-key', 'Content-Type': 'application/json' },
      ...(data === undefined ? {} : { body: JSON.stringify(data) }),
    });
    for (const [index, legacy] of [[1, false], [2, true]]) {
      const artifact = JSON.parse(await readFile(`test/fixtures/${index}.json`, 'utf8'));
      const created = await req('/api/publications', { artifact, reviewed: true });
      assert.equal(created.status, 201, await created.clone().text());
      const { id } = await created.json();
      const { object_key: key } = await db.prepare('SELECT object_key FROM publications WHERE id=?').bind(id).first();
      assert.equal((await bucket.list({ prefix: key })).objects.length, 2);
      if (legacy) {
        const oldKey = 'publications/' + id + '/legacy';
        await bucket.put(oldKey, JSON.stringify(artifact));
        await db.prepare('UPDATE publications SET object_key=? WHERE id=?').bind(oldKey, id).run();
        await bucket.delete([key + '/bundle', key + '/player']);
      }
      for (const [part, expected] of [['bundle', artifact.inquiry_json], ['player', artifact.player_json]]) {
        const response = await req(`/api/publications/${id}/${part}`);
        assert.equal(response.status, 200);
        assert.equal(response.headers.get('Cache-Control'), 'no-store');
        assert.equal(await response.text(), expected);
      }
      const retry = await req('/api/publications', { artifact, reviewed: true });
      assert.equal(retry.status, 200);
      assert.equal((await retry.json()).reused, true);
      assert.equal((await bucket.list()).objects.length, legacy ? 1 : 2);
      assert.equal((await req(`/api/publications/${id}/withdraw`, {})).status, 200);
      assert.equal((await bucket.list()).objects.length, 0);
      assert.equal((await req(`/api/publications/${id}/bundle`)).status, 410);
    }
    const oversized = '{"padding":"' + 'x'.repeat(MAX_BYTES) + '"}';
    const rejected = await mf.dispatchFetch('http://localhost:7490/api/publications', {
      method: 'POST', headers: { Authorization: 'Bearer synthetic-key', 'Content-Type': 'application/json' }, body: oversized,
    });
    assert.equal(rejected.status, 413);
    assert.equal((await bucket.list()).objects.length, 0);
  } finally { await mf.dispose(); }
});

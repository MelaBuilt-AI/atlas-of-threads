const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const music = fs.readFileSync(path.join(__dirname, '../viz/dist/music.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

// Synthetic media/DOM boundary: exercise the real player handlers without
// downloading music or requiring an audio device in CI.
function player(saved = {}) {
  const elements = new Map();
  class Element {
    constructor() { this.listeners = {}; this.children = []; this.dataset = {}; this.paused = true; this.attributes = {}; }
    addEventListener(event, handler) { (this.listeners[event] ||= []).push(handler); }
    fire(event, detail = {}) { for (const handler of this.listeners[event] || []) handler({target:this, ...detail}); }
    click() { this.fire('click'); }
    setAttribute(key, value) { this.attributes[key] = value; }
    replaceChildren() { this.children = []; }
    append(child) { this.children.push(child); }
    contains(target) { return target === this; }
    async play() { if (this.failure) throw this.failure; this.paused = false; }
    pause() { this.paused = true; }
  }
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const storage = {'atlas.music.v1':JSON.stringify(saved)};
  const revoked = [];
  let url = 0;
  const window = new Element();
  vm.runInNewContext(music, {
    document: {getElementById:get, createElement:() => new Element(), querySelectorAll:() => []}, window,
    localStorage: {getItem:key => storage[key], setItem:(key,value) => {storage[key]=value;}},
    URL: {createObjectURL:() => `blob:synthetic-${++url}`, revokeObjectURL:url => revoked.push(url)},
  });
  return {get, window, storage, revoked, audio:get('atlas-music')};
}
const song = name => ({name, type:'audio/ogg'});
const playlist = (name, text) => ({name, type:'', text:async () => text});
async function load(p, files) { p.get('music-files').files=files; p.get('music-files').fire('change'); await flush(); }

test('title starts first, all thirteen tracks advance and wrap, previous wraps backward', async () => {
  const p = player(); await flush();
  assert.match(p.audio.src, /01-atlas-of-threads-title/);
  assert.equal(p.audio.paused, false);
  for (let i=1; i<=13; i++) {
    p.audio.fire('ended'); await flush();
    assert.equal(p.get('music-track').value, String(i%13));
  }
  p.get('music-previous').click(); await flush();
  assert.match(p.audio.src, /13-where-the-threads-begin-again/);
  const folder = path.join(__dirname, '../viz/dist/assets/audio/music');
  assert.equal(fs.readdirSync(folder).filter(x=>x.endsWith('.ogg')).length, 13);
  assert.equal(p.get('music-track').children.length, 13);
});

test('volume persists, each launch autoplays, and in-session skips respect pause without changing effects', async () => {
  const p = player(); await flush();
  p.get('music-toggle').click();
  p.get('music-next').click(); await flush();
  assert.equal(p.audio.paused, true);
  assert.equal(JSON.parse(p.storage['atlas.music.v1']).paused, undefined);
  p.get('music-volume').value='17'; p.get('music-volume').fire('input');
  assert.equal(p.audio.volume, .17);
  assert.deepEqual(Object.keys(p.storage), ['atlas.music.v1']);
  const restored=player(JSON.parse(p.storage['atlas.music.v1'])); await flush();
  assert.equal(restored.audio.paused,false);
  assert.equal(restored.audio.volume,.17);
  const legacy=player({paused:true,volume:.17}); await flush();
  assert.equal(legacy.audio.paused,false);
  assert.equal(legacy.audio.volume,.17);
});

test('M3U preserves track order, skips missing files and releases local URLs on album return', async () => {
  const p=player(); p.get('music-toggle').click();
  await load(p, [song('a.ogg'), song('b.ogg'), playlist('mix.m3u', '#EXTM3U\n#EXTINF:1,Second song\nb.ogg\nmissing.ogg\na.ogg')]);
  assert.deepEqual(p.get('music-track').children.map(x=>x.textContent), ['1 · Second song','2 · a']);
  assert.match(p.get('music-import-status').textContent,/1 missing/);
  assert.equal(p.audio.paused,true);
  p.get('music-album').click();
  assert.equal(p.revoked.length,2);
  assert.match(p.audio.src,/01-atlas/);
});

test('PLS handles local Windows paths, explicit web streams and failed imports leave the queue intact', async () => {
  const p=player(); p.get('music-toggle').click();
  await load(p,[song('a.ogg'),playlist('mix.pls','[playlist]\nFile2=https://example.invalid/stream\nTitle2=Stream\nFile1=C:\\Music\\a.ogg\nTitle1=Local')]);
  assert.deepEqual(p.get('music-track').children.map(x=>x.textContent), ['1 · Local','2 · Stream']);
  const src=p.audio.src;
  await load(p,[playlist('missing.m3u','/missing/song.ogg\njavascript:alert(1)')]);
  assert.equal(p.audio.src,src);
  assert.match(p.get('music-import-status').textContent,/No playable tracks/);
});

test('blocked autoplay resumes on interaction; a bad track stops without an endless skip loop', async () => {
  const p=player(); await flush();
  p.audio.failure={name:'NotAllowedError'};
  p.get('music-next').click(); await flush();
  assert.match(p.get('music-status').textContent,/first click/);
  p.audio.failure=null;
  p.window.fire('pointerdown'); await flush();
  assert.equal(p.audio.paused,false);
  p.audio.failure={name:'NotSupportedError'};
  p.get('music-next').click(); await flush();
  assert.match(p.get('music-status').textContent,/could not play/);
  const src=p.audio.src;
  p.audio.fire('ended'); await flush();
  assert.equal(p.audio.src,src);
});


test('entering or explicitly resuming a Threadwalk picks another track; chambers keep playing', async () => {
  const p=player(); await flush();
  let previous=p.audio.src;
  for (let i=0;i<30;i++) {
    p.window.TAMusic.enterThreadwalk(`synthetic-${i}`); await flush();
    assert.notEqual(p.audio.src,previous);
    assert.equal(p.audio.paused,false);
    previous=p.audio.src;
    p.audio.currentTime=42;
    p.window.TAMusic.enterThreadwalk(`synthetic-${i}`); await flush();
    assert.equal(p.audio.src,previous);
    assert.equal(p.audio.currentTime,42);
  }
  p.window.TAMusic.enterThreadwalk('synthetic-29',true); await flush();
  assert.notEqual(p.audio.src,previous);
  p.get('music-toggle').click();
  p.window.TAMusic.enterThreadwalk('synthetic-30'); await flush();
  assert.equal(p.audio.paused,true);
});

test('Threadwalk music uses the loaded playlist without unpausing it', async () => {
  const p=player(); await flush(); p.get('music-toggle').click();
  await load(p,[song('a.ogg'),song('b.ogg')]);
  const previous=p.audio.src;
  p.window.TAMusic.enterThreadwalk('synthetic-custom'); await flush();
  assert.notEqual(p.audio.src,previous);
  assert.match(p.audio.src,/blob:/);
  assert.equal(p.get('music-source').textContent,'Your music');
  assert.equal(p.audio.paused,true);
  p.get('music-toggle').click(); await flush();
  assert.equal(p.audio.paused,false);
});

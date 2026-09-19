// Bounded, local-only capacity receipt. Does not estimate hosted Worker CPU.
import {Miniflare} from 'miniflare';
import {readFile,readdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
const mf=new Miniflare({modules:true,scriptPath:'dist/worker.js',compatibilityDate:'2026-05-15',d1Databases:['DB'],r2Buckets:['INQUIRIES'],bindings:{SITE_ORIGIN:'https://synthetic.example'}});
try {
 const db=await mf.getD1Database('DB');
 for(const file of (await readdir('migrations')).filter(f=>f.endsWith('.sql')).sort())for(const sql of (await readFile('migrations/'+file,'utf8')).split(';').map(s=>s.trim()).filter(Boolean))await db.prepare(sql).run();
 for(let n=0;n<25;n++)await db.prepare('INSERT INTO owners VALUES(?,?,?,1)').bind('synthetic-'+n,'Synthetic '+n,'synthetic').run();
 // 25 owners at the preview's 20-publication quota: 500 locales, five pages.
 for(let start=1;start<=500;start+=50)await db.batch(Array.from({length:50},(_,i)=>{const n=start+i,id=n.toString(16).padStart(64,'0');return db.prepare(`INSERT INTO publications(id,owner_id,inquiry_id,origin_id,session_id,title,author,description,graph_count,thought_count,object_key,created_at,threadwalk_id)
 VALUES(?,?,?,'synthetic',?,'Synthetic capacity inquiry','Synthetic author','Synthetic capacity fixture',1,3,?,1,?)`).bind(id,'synthetic-'+Math.floor((n-1)/20),id,id,id,id);}));
 const times=[],ids=new Set();let cursor=0,pages=0,totalBytes=0;
 do{const t=performance.now(),r=await mf.dispatchFetch('https://synthetic.example/api/world?after='+cursor),body=await r.text();times.push(performance.now()-t);assert.equal(r.status,200);totalBytes+=Buffer.byteLength(body);const page=JSON.parse(body);assert.ok(page.publications.length<=100);for(const p of page.publications){assert.ok(!ids.has(p.id));ids.add(p.id);}cursor=page.next;pages++;}while(cursor);
 assert.equal(ids.size,500);
 const concurrent=await Promise.all(Array.from({length:20},async()=>{const t=performance.now(),r=await mf.dispatchFetch('https://synthetic.example/api/world');assert.equal(r.status,200);await r.arrayBuffer();return performance.now()-t;}));
 console.log(JSON.stringify({environment:'local Miniflare; not hosted CPU or device rendering',owners:25,publications:500,pages,total_response_bytes:totalBytes,page_ms:times.map(n=>Math.round(n)),concurrent_readers:20,concurrent_max_ms:Math.round(Math.max(...concurrent)),complete:true},null,2));
}finally{await mf.dispose();}

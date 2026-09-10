"""Generate six explicitly synthetic publication fixtures; never opens a user store."""
from pathlib import Path
from thought_archaeology import portable
from thought_archaeology.online import prepare_publication
from thought_archaeology.models import ThoughtGraph

root = Path(__file__).resolve().parents[1] / 'test' / 'fixtures'
root.mkdir(exist_ok=True)
subjects = [
 ('The medium and the microscope', 'An inspectable thought is a useful medium without pretending to be a neural trace.', 'Visible claims help us discuss an answer.', 'An explanation can omit the mechanisms that produced it.'),
 ('A doorway that remembers', 'A returned path should preserve the exact thought that invited it.', 'Stable source identities make returning meaningful.', 'Acceptance adds a new doorway without rewriting the first answer.'),
 ('Where a question branches', 'A fork can preserve both a decision and the alternative it leaves behind.', 'Keeping an alternative makes comparison possible.', 'A different starting premise may change which path is useful.'),
 ('The quiet between visits', 'A shared inquiry should remain readable when its publisher is offline.', 'A reviewed snapshot can be stored separately from a private Atlas.', 'Private work does not need to become a live public feed.'),
 ('The shape of uncertainty', 'An uncertainty can be a destination worth entering.', 'Naming a limit gives a later inquiry somewhere precise to begin.', 'A visible question is not evidence that its answer is known.'),
 ('Bringing a thread home', 'A visitor can carry a public inquiry into a private conversation.', 'A portable copy preserves attribution and source references.', 'Asking a local guide and publishing a response are separate choices.'),
]
for index, (title, claim, premise, uncertainty) in enumerate(subjects):
    uid = lambda n: str(index * 100 + n).zfill(26)
    date = '2026-09-10T00:00:00Z'
    graph = {'schema_version':'1.0.0','id':uid(2),'session_id':uid(1),'turn_id':uid(3),'created_at':date,
             'prose':f'{claim}\n\n{premise}\n\n{uncertainty}\n\nSynthetic example authored by Codex for the online Atlas preview.',
             'model':{'provider':'none','name':'Synthetic preview · Codex','compile_mode':'structured_emit'},
             'nodes':[{'id':uid(10+n),'kind':kind,'text':text,'status':'uncertain' if kind=='uncertainty' else 'accepted',
                       'agent':'human','created_at':date,'source':'human','confidence':1.0 if n==0 else 0.00001}
                       for n,(kind,text) in enumerate([('claim',claim),('premise',premise),('uncertainty',uncertainty)])],
             'edges':[{'id':uid(20),'source_id':uid(11),'target_id':uid(10),'kind':'supports','created_at':date},
                      {'id':uid(21),'source_id':uid(12),'target_id':uid(10),'kind':'qualifies','created_at':date}]}
    public = portable.project_graph(ThoughtGraph.from_dict(graph))
    content = {'origin_id':uid(0),'author':'Synthetic publisher','description':'A synthetic inquiry for exploring the online Atlas preview.',
               'session':{'id':uid(1),'title':title,'created_at':date,'updated_at':date,'head_graph_id':uid(2)},
               'graphs':[{'graph':public,'source_sha256':portable.digest(graph),'shared_sha256':portable.digest(public),'role':'assistant','source':None}],
               'evidence':[], 'omitted_evidence_count':0}
    bundle = {'format':'atlas-inquiry','version':1,'id':portable.digest(content),'content':content}
    (root / f'{index+1}.json').write_bytes(portable.canonical(prepare_publication(bundle)))
print('Generated six synthetic publication fixtures.')

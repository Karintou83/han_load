import sys,hashlib,json
S=["\tP39\t","\tP580\t+","-00-00T00:00:00Z/9","\tP582\t+","\tP1365\t","\tP1366\t","\tP2388\t","\tP301\t","\tP22\t","\tP40\t","\tP1038\t","\tP1039\t"]
def enc(l):
    for i,s in enumerate(S): l=l.replace(s,"§"+chr(65+i))
    return l
def chunks(f,n):
    L=open(f,encoding='utf-8').read().splitlines()
    return [L[i:i+n] for i in range(0,len(L),n)]
out=[]
for name,f,n in [("recip","kinki_stage2_recip.tsv",200),("p39","kinki_stage2_p39.tsv",240),("fam","kinki_stage2_family_ok.tsv",260)]:
    for k,c in enumerate(chunks(f,n)):
        t="\n".join(c)
        out.append({"id":f"{name}{k+1}","n":len(c),"sha":hashlib.sha256(t.encode()).hexdigest()[:16],"d":"|".join(enc(x) for x in c)})
json.dump(out,open("kinki_stage2_batches.json","w"),ensure_ascii=False)
for o in out: print(o['id'],o['n'],o['sha'],len(o['d']))


import re, itertools
from collections import Counter
import pandas as pd

def norm_ref(x):
    s=re.sub(r"[^A-Z0-9]","",str(x).upper())
    for p in ("INVOICE","INV","CREDITNOTE","CREDIT","CN"):
        if s.startswith(p): s=s[len(p):]; break
    m=re.fullmatch(r"0*(\d+)",s)
    return m.group(1) if m else s

def prep(df,m):
    x=df.copy()
    x["_ref"]=x[m["ref"]].map(norm_ref)
    x["_amt"]=pd.to_numeric(x[m["amount"]],errors="coerce")
    x["_cur"]=x[m["currency"]].astype(str).str.upper().str.strip() if m.get("currency") else "DEFAULT"
    x["_date"]=pd.to_datetime(x[m["date"]],errors="coerce") if m.get("date") else pd.NaT
    return x

def group_candidates(target, pool, tol, max_group=3):
    vals=[(i,float(r["_amt"])) for i,r in pool.iterrows()]
    for n in range(2,min(max_group,len(vals))+1):
        for comb in itertools.combinations(vals,n):
            if abs(sum(v for _,v in comb)-float(target))<=tol:
                return [i for i,_ in comb]
    return []

def reconcile(S,L,sm,lm,tol=.01,date_days=7):
    S,L=prep(S,sm),prep(L,lm)
    usedS=set(); usedL=set(); rows=[]
    dupL=Counter(zip(L["_ref"],L["_amt"],L["_cur"]))

    # 1:1 exact / amount mismatch
    for si,s in S.iterrows():
        cand=L[(L["_ref"]==s["_ref"])&(L["_cur"]==s["_cur"])&(~L.index.isin(usedL))]
        exact=cand[(cand["_amt"]-s["_amt"]).abs()<=tol]
        if len(exact):
            li=exact.index[0]; l=L.loc[li]; usedS.add(si); usedL.add(li)
            st="POSSIBLE_DUPLICATE" if dupL[(l["_ref"],l["_amt"],l["_cur"])]>1 else "EXACT"
            rows.append([si,str(s[sm["ref"]]),str(li),str(l[lm["ref"]]),s["_amt"],l["_amt"],s["_cur"],st,"HIGH","1:1 reference + amount + currency"])
        elif len(cand)==1:
            li=cand.index[0]; l=L.loc[li]; usedS.add(si); usedL.add(li)
            rows.append([si,str(s[sm["ref"]]),str(li),str(l[lm["ref"]]),s["_amt"],l["_amt"],s["_cur"],"AMOUNT_MISMATCH","HIGH",f"Same reference; difference {s['_amt']-l['_amt']:.2f}"])

    # 1:N: statement line equals several ledger lines; review only
    for si,s in S.loc[~S.index.isin(usedS)].iterrows():
        pool=L[(L["_cur"]==s["_cur"])&(~L.index.isin(usedL))]
        if pd.notna(s["_date"]):
            pool=pool[(pool["_date"].isna())|((pool["_date"]-s["_date"]).abs().dt.days<=date_days)]
        ids=group_candidates(s["_amt"],pool,tol,3)
        if ids:
            refs=" + ".join(str(L.loc[i,lm["ref"]]) for i in ids)
            am=sum(float(L.loc[i,"_amt"]) for i in ids)
            rows.append([si,str(s[sm["ref"]]),",".join(map(str,ids)),refs,s["_amt"],am,s["_cur"],"GROUP_1_TO_N","MEDIUM","Grouped amount candidate; requires review"])
            usedS.add(si) # don't consume ledger candidates until reviewer confirms

    # N:1: several statement lines equal one ledger line; review only
    for li,l in L.loc[~L.index.isin(usedL)].iterrows():
        pool=S[(S["_cur"]==l["_cur"])&(~S.index.isin(usedS))]
        if pd.notna(l["_date"]):
            pool=pool[(pool["_date"].isna())|((pool["_date"]-l["_date"]).abs().dt.days<=date_days)]
        ids=group_candidates(l["_amt"],pool,tol,3)
        if ids:
            refs=" + ".join(str(S.loc[i,sm["ref"]]) for i in ids)
            am=sum(float(S.loc[i,"_amt"]) for i in ids)
            rows.append([",".join(map(str,ids)),refs,li,str(l[lm["ref"]]),am,l["_amt"],l["_cur"],"GROUP_N_TO_1","MEDIUM","Grouped amount candidate; requires review"])
            for i in ids: usedS.add(i)

    # remaining
    for si,s in S.loc[~S.index.isin(usedS)].iterrows():
        st="UNAPPLIED_CREDIT" if s["_amt"]<0 else "MISSING_IN_AP"
        rows.append([si,str(s[sm["ref"]]),"","",s["_amt"],"",s["_cur"],st,"HIGH","No eligible AP match"])
    for li,l in L.loc[~L.index.isin(usedL)].iterrows():
        st="POSSIBLE_DUPLICATE" if dupL[(l["_ref"],l["_amt"],l["_cur"])]>1 else "MISSING_ON_STATEMENT"
        rows.append(["","",li,str(l[lm["ref"]]),"",l["_amt"],l["_cur"],st,"HIGH","Not consumed by deterministic 1:1 match"])

    return pd.DataFrame(rows,columns=["Statement Row","Statement Ref","AP Row(s)","AP Ref(s)","Statement Amount","AP Amount","Currency","Status","Confidence","Reason"])

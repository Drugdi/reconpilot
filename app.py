
import io,re
import pandas as pd
import streamlit as st
from engine import reconcile

st.set_page_config(page_title="ReconPilot v0.4",page_icon="✓",layout="wide")
st.title("ReconPilot")
st.subheader("Find supplier-statement exceptions in minutes")
st.caption("Upload a supplier statement and AP ledger. Get deterministic matches and a review-ready exception list.")
st.markdown("**Free:** scan and summary. **Full workpaper:** configurable paid upgrade for validation testing.")

def read_file(f):
    return pd.read_csv(f) if f.name.lower().endswith(".csv") else pd.read_excel(f)
def clean(s): return re.sub(r"[^a-z0-9]","",str(s).lower())
def guess(cols,terms):
    for t in terms:
        for c in cols:
            if clean(t) in clean(c): return c
def mapui(df,key):
    cols=list(df.columns); none=["(none)"]+cols
    def sel(label,terms,optional=False):
        g=guess(cols,terms); opts=none if optional else cols
        idx=opts.index(g) if g in opts else 0
        v=st.selectbox(f"{key} {label}",opts,index=idx,key=key+label)
        return None if v=="(none)" else v
    return {"ref":sel("reference",["invoice ref","document ref","invoice","reference"]),
            "amount":sel("amount",["amount","total","balance"]),
            "date":sel("date",["invoice date","document date","date"],True),
            "currency":sel("currency",["currency","ccy"],True)}

a,b=st.columns(2)
with a: sf=st.file_uploader("Supplier statement",["xlsx","xls","csv"])
with b: lf=st.file_uploader("AP ledger",["xlsx","xls","csv"])
if sf and lf:
    S,L=read_file(sf),read_file(lf)
    a,b=st.columns(2)
    with a: sm=mapui(S,"Statement")
    with b: lm=mapui(L,"Ledger")
    c,d=st.columns(2)
    tol=c.number_input("Amount tolerance",0.0,1000.0,.01,.01)
    days=d.number_input("Grouped-match date window",0,365,7,1)
    if st.button("Run reconciliation",type="primary"):
        R=reconcile(S,L,sm,lm,tol,days)
        exact=int((R.Status=="EXACT").sum())
        grouped=int(R.Status.isin(["GROUP_1_TO_N","GROUP_N_TO_1"]).sum())
        exc=int((R.Status!="EXACT").sum())
        m=st.columns(4)
        m[0].metric("Statement rows",len(S));m[1].metric("Exact",exact);m[2].metric("Grouped review",grouped);m[3].metric("Exceptions",exc)
        preview=R[R.Status!="EXACT"].head(8)
        st.markdown("### Free exception preview")
        st.dataframe(preview,use_container_width=True,height=330)

        bio=io.BytesIO()
        with pd.ExcelWriter(bio,engine="openpyxl") as w:
            R.to_excel(w,index=False,sheet_name="Reconciliation")
            R.Status.value_counts().rename_axis("Status").reset_index(name="Count").to_excel(w,index=False,sheet_name="Summary")
            S.to_excel(w,index=False,sheet_name="Statement Source")
            L.to_excel(w,index=False,sheet_name="AP Source")

        payment_url=""
        try: payment_url=st.secrets.get("PAYMENT_URL","")
        except Exception: pass
        if payment_url:
            st.link_button("Unlock full workpaper — €49",payment_url,type="primary")
            st.caption("Payment link is configured by the operator. Deliver the full workpaper only for a product/service you can actually provide.")
        else:
            st.download_button("Download full workpaper (test mode)",bio.getvalue(),"reconpilot_workpaper.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            st.caption("Test mode: add PAYMENT_URL in Streamlit secrets before running a paid validation.")

        st.info("Grouped matches are candidates only and require reviewer confirmation. ReconPilot does not approve payments or post to ERP.")

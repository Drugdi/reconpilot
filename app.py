import io
import re

import pandas as pd
import streamlit as st
import stripe

from engine import reconcile


st.set_page_config(
    page_title="ReconPilot v0.4",
    page_icon="✓",
    layout="wide",
)

st.title("ReconPilot")
st.subheader("Find supplier-statement exceptions in minutes")
st.caption(
    "Upload a supplier statement and AP ledger. "
    "Get deterministic matches and a review-ready exception list."
)
st.markdown(
    "**Free:** scan and summary. "
    "**Full workpaper:** configurable paid upgrade for validation testing."
)


# -------------------------
# Stripe payment verification
# -------------------------

paid = False
session_id = st.query_params.get("session_id", "")

if session_id:
    try:
        stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]

        checkout_session = stripe.checkout.Session.retrieve(session_id)

        if checkout_session.payment_status == "paid":
            paid = True
            st.success(
                "Payment confirmed ✓ Upload the two files and run reconciliation "
                "to download the full workpaper."
            )
        else:
            st.warning("Payment has not been confirmed.")
    except Exception:
        st.error("Unable to verify payment with Stripe.")


# -------------------------
# Helpers
# -------------------------

def read_file(f):
    if f.name.lower().endswith(".csv"):
        return pd.read_csv(f)
    return pd.read_excel(f)


def clean(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def guess(cols, terms):
    for term in terms:
        for col in cols:
            if clean(term) in clean(col):
                return col
    return None


def mapui(df, key):
    cols = list(df.columns)
    none = ["(none)"] + cols

    def sel(label, terms, optional=False):
        guessed = guess(cols, terms)
        options = none if optional else cols

        if guessed in options:
            index = options.index(guessed)
        else:
            index = 0

        value = st.selectbox(
            f"{key} {label}",
            options,
            index=index,
            key=key + label,
        )

        return None if value == "(none)" else value

    return {
        "ref": sel(
            "reference",
            ["invoice ref", "document ref", "invoice", "reference"],
        ),
        "amount": sel(
            "amount",
            ["amount", "total", "balance"],
        ),
        "date": sel(
            "date",
            ["invoice date", "document date", "date"],
            True,
        ),
        "currency": sel(
            "currency",
            ["currency", "ccy"],
            True,
        ),
    }


# -------------------------
# Upload files
# -------------------------

left, right = st.columns(2)

with left:
    sf = st.file_uploader(
        "Supplier statement",
        ["xlsx", "xls", "csv"],
    )

with right:
    lf = st.file_uploader(
        "AP ledger",
        ["xlsx", "xls", "csv"],
    )


# -------------------------
# Reconciliation
# -------------------------

if sf and lf:
    S = read_file(sf)
    L = read_file(lf)

    left, right = st.columns(2)

    with left:
        sm = mapui(S, "Statement")

    with right:
        lm = mapui(L, "Ledger")

    col1, col2 = st.columns(2)

    tolerance = col1.number_input(
        "Amount tolerance",
        0.0,
        1000.0,
        0.01,
        0.01,
    )

    days = col2.number_input(
        "Grouped-match date window",
        0,
        365,
        7,
        1,
    )

    if st.button("Run reconciliation", type="primary"):
        R = reconcile(
            S,
            L,
            sm,
            lm,
            tolerance,
            days,
        )

        exact = int((R.Status == "EXACT").sum())

        grouped = int(
            R.Status.isin(
                ["GROUP_1_TO_N", "GROUP_N_TO_1"]
            ).sum()
        )

        exceptions = int(
            (R.Status != "EXACT").sum()
        )

        metrics = st.columns(4)

        metrics[0].metric(
            "Statement rows",
            len(S),
        )

        metrics[1].metric(
            "Exact",
            exact,
        )

        metrics[2].metric(
            "Grouped review",
            grouped,
        )

        metrics[3].metric(
            "Exceptions",
            exceptions,
        )

        preview = R[
            R.Status != "EXACT"
        ].head(8)

        st.markdown("### Free exception preview")

        st.dataframe(
            preview,
            use_container_width=True,
            height=330,
        )

        # -------------------------
        # Build full Excel workpaper
        # -------------------------

        bio = io.BytesIO()

        with pd.ExcelWriter(
            bio,
            engine="openpyxl",
        ) as writer:

            R.to_excel(
                writer,
                index=False,
                sheet_name="Reconciliation",
            )

            (
                R.Status
                .value_counts()
                .rename_axis("Status")
                .reset_index(name="Count")
                .to_excel(
                    writer,
                    index=False,
                    sheet_name="Summary",
                )
            )

            S.to_excel(
                writer,
                index=False,
                sheet_name="Statement Source",
            )

            L.to_excel(
                writer,
                index=False,
                sheet_name="AP Source",
            )

        bio.seek(0)

        # -------------------------
        # Paid / unpaid state
        # -------------------------

        payment_url = ""

        try:
            payment_url = st.secrets.get(
                "PAYMENT_URL",
                "",
            )
        except Exception:
            pass

        if paid:
            st.success(
                "Full workpaper unlocked ✓"
            )

            st.download_button(
                "Download full workpaper",
                data=bio.getvalue(),
                file_name="ReconPilot_Reconciliation.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                type="primary",
            )

        elif payment_url:
            st.link_button(
                "Unlock full workpaper — €49",
                payment_url,
                type="primary",
            )

        else:
            st.warning(
                "Payment link is not configured."
            )
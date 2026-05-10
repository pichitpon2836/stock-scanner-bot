        # ── Buffett Filter ─────────────────────
        roe    = info.get("returnOnEquity")
        debt_eq = info.get("debtToEquity")
        if roe is None or debt_eq is None:
            return None
        debt_eq = debt_eq / 100.0
        if not (roe * 100 > 10 and debt_eq < 2.0):
            return None

        # ── Lynch Filter ───────────────────────
        growth = info.get("earningsGrowth")
        if growth is None or growth * 100 < 0:
            return None

        # ── Nick Sleep Filter ──────────────────
        fcf_list = []
        try:
            cf = tk.cashflow
            if cf is not None and not cf.empty:
                for label in ["Free Cash Flow", "freeCashFlow"]:
                    if label in cf.index:
                        fcf_list = cf.loc[label].dropna().values[:1].tolist()
                        break
        except:
            pass
        if not fcf_list or fcf_list[0] <= 0:
            return None

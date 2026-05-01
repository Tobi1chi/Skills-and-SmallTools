# API Notes

The CLI uses public catalog surfaces first and official/authenticated sources only when configured.

## Source order

Default `auto` mode:

1. SZLCSC public search page:
   `GET https://so.szlcsc.com/global.html?k={QUERY}`
2. JLCPCB public SMT component search fallback:
   `POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2`
3. LCSC official keyword API fallback only when credentials are available:
   `LCSC_API_KEY` and `LCSC_API_SECRET`
4. EasyEDA component metadata only after a specific LCSC code exists:
   `GET https://easyeda.com/api/products/{LCSC_CODE}/components?version=6.4.19.5`

## Operational rules

- Do not scrape authenticated user pages.
- Treat missing fields, WAF pages, schema changes, and HTTP errors as normal data-source failures.
- Keep source names and raw identifiers in output for auditability.
- Do not persist cache unless the user explicitly asks.
- Do not infer electrical suitability from catalog presence.

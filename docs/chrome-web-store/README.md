# Chrome Web Store publication

Build the submission ZIP from a clean release checkout:

```bash
python3 scripts/package_extension.py --browser chrome
```

The package contains only runtime files, image assets and license notices. Its manifest is Chrome-specific; Firefox background configuration and development tests are excluded. The ZIP has `manifest.json` at its root and validates the four installation icon sizes.

Use [listing.md](listing.md) for the store text, permission justifications, data disclosures and reviewer instructions. Public privacy and support pages are served by the API at `/privacy` and `/support`. Validate the deployed pages before entering their URLs in the dashboard.

The in-page Solve button works on the first visit without opening the toolbar. Chrome's capture API requires `<all_urls>` for this flow; this broader host permission must be disclosed in the listing. Capture code rejects inactive tabs and URLs outside supported HTTPS LinkedIn games. Content scripts only match LinkedIn. The extension does not request the `tabs` permission. Custom API addresses remain user-selected; because the capture permission already grants host access, an additional host prompt is normally unnecessary.

The existing LinkedIn-derived artwork needs an explicit distribution-rights decision before store submission. Attribution does not grant redistribution rights. Do not label the product as official or endorsed by LinkedIn.

The publisher owner must complete registration, payment and legal agreements. Do not put payment details, account credentials or publishing tokens in Git. A store upload or a GitHub release does not mean Google has approved the extension.

Official references: [prepare a package](https://developer.chrome.com/docs/webstore/prepare), [image requirements](https://developer.chrome.com/docs/webstore/images), [privacy fields](https://developer.chrome.com/docs/webstore/cws-dashboard-privacy), [registration](https://developer.chrome.com/docs/webstore/register).

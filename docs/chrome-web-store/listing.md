# Chrome Web Store listing draft

## Store listing

- Name: Puzzle Solver for LinkedIn Games (public identity pending confirmation).
- Language: English.
- Category: Tools.
- Price to users: Free.
- Homepage: https://linkedin-puzzle-solvers.vercel.app/
- Support: https://linkedin-puzzle-solvers.vercel.app/support
- Privacy: https://linkedin-puzzle-solvers.vercel.app/privacy
- Publisher name and public support email: pending owner's confirmation.

Short description:

> Preview and apply solutions for six LinkedIn games using the online solver or your own local API.

Detailed description:

> Get help with Queens, Tango, Mini Sudoku, Zip, Patches and Wend on LinkedIn Games.
>
> Open a game and click its in-page Solve button, or open Puzzle Solver in Chrome's toolbar and choose Preview solution or Solve & apply. Automatic board detection locates the puzzle; manual selection is available when needed.
>
> Online mode uses our hosted solver without installing Python or Docker. Local mode supports your own API. Saved local settings stay available when switching modes.
>
> Online sends the selected board image to our service over HTTPS. The hosted application does not archive uploads. See the privacy policy for processing, temporary files and hosting metadata. A custom service has its own retention settings.
>
> Keep the complete board visible. The extension can scroll a partly hidden board into view and stops when it cannot verify supported game input. Availability and recognition can be affected by game updates.
>
> Independent open-source project. Not affiliated with or endorsed by LinkedIn. LinkedIn and game names belong to their respective owners.

## Privacy practices

Single purpose:

> Help users preview and apply solutions to the six supported LinkedIn Games, using a hosted or user-selected local solver.

Permission justifications:

| Permission | Reason |
| --- | --- |
| activeTab | Support temporary access when the user invokes the extension toolbar. |
| `<all_urls>` host access | Chrome requires this permission to capture from the in-page Solve button without prior toolbar activation. The capture code accepts only active supported HTTPS LinkedIn game tabs; content scripts only match LinkedIn. This permission technically grants broader host access. |
| scripting | Inject the bundled game helpers into the active supported page or frame when they are not already available. No downloaded JavaScript is injected. |
| storage | Save service addresses, game selection, board selection, last solution and timing preferences locally. |
| webNavigation | Locate LinkedIn game iframes and translate board coordinates between them and the top page. |
| LinkedIn hosts | Detect visible game boards, display previews and apply verified moves on supported game pages. |
| Hosted API | Send the selected cropped board image to the online solver and receive its solution. |
| localhost / 127.0.0.1 | Communicate with the user's local solver. |
| Optional HTTP/HTTPS hosts | Support a user-selected custom API host if access is not already granted. With the capture host permission, a separate prompt is normally unnecessary. |

Remote code declaration:

> No remotely hosted JavaScript or WebAssembly is downloaded or executed. The server performs puzzle solving and returns JSON puzzle data; all browser interaction logic is bundled in the extension.

Data disclosures to select:

- Website content: visible board elements and the cropped selected game image.
- Web history: only the current supported game URL is read to identify the game. This local use is disclosed even though no browsing-history list is requested or retained.
- Personally identifiable information: Vercel processes request IP addresses as hosting metadata; the extension does not request names, emails or account identifiers.
- No credentials, personal communications, financial information or advertising identifiers are requested by the extension.
- Hosting infrastructure receives ordinary network metadata; do not claim that no data leaves the browser.

Confirm the declarations match the deployed privacy page and actual package before submission. No sale, advertising, unrelated use or creditworthiness use of user data.

## Reviewer instructions

1. Open https://www.linkedin.com/games/ and start any supported game. A fresh guest/incognito game can be used when the current daily puzzle was already completed.
2. Click the in-page Solve button immediately to verify first-use capture. Default service is Online. The toolbar provides preferences and preview controls.
3. Keep the board visible and click Preview solution to inspect an overlay, or Solve & apply to populate the game.
4. If a capture is wrong, use Board tools → Detect board or Select area. Reset a puzzle containing incorrect previous entries before solving again.
5. Local mode is optional. Testing Online does not require installing a server, Docker, or a separate account for this extension.
6. A site's own login/availability requirements can change. Provide additional reviewer access instructions if the current LinkedIn experience requires them; never put account passwords in this repository.

## Remaining owner steps

- Confirm the public publisher name/support email and artwork rights or choose an independent identity.
- Complete Chrome Web Store registration, its legal agreement, any identity/account verification, and the one-time registration payment.
- Upload the generated Chrome ZIP, installation icon and at least one accurate screenshot.
- Complete the listing, privacy declarations, distribution and reviewer instructions.
- Submit for review after all fields and assets are final. Store approval is decided by Google.

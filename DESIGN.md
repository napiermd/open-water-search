# Open Water Search design

The site matches the editorial pages of the papercraft video (`outputs/water-probe/video/papercraft-full/render.py` in the working folder). The Lake Michigan miniature has its own palette and appears only as the labeled illustration of the officer's account.

## Colour

| Role | Value |
| --- | --- |
| Page stock | #EADDBE |
| Photo mounts, cards, light type | #F5E9CD |
| Navy ink and solid panels | #153642 |
| Dark evidence page (textured) | #153641 |
| Accent, detector + Ember | #FF9962 |
| Accent, detector alone | #9CD6C8 |
| Divider | #68948E |
| Cast shadow on stock / on navy | #526965 / #08232B |
| Cut edge / exposed fold face | #B29C7E / #B8A580 |

In handoffs both pins carry explicit crew labels.

## Type

- Anton Regular: sentence-case headlines, slot values, result tags and calls to action.
- Libre Caslon Text Italic: the officer's words and occasional story lines.
- Helvetica Neue: explanatory copy.
- Menlo: provenance, IDs and photo labels. Uppercase metadata uses spaced slashes, as in OFFICER'S ACCOUNT / LAKE MICHIGAN.
- Native tracking. At 1280 px wide: headline 58 px, metadata 20 px, photo labels 22 px.

## Material

Static monochrome grain (σ 2.4/255) and faint broad tonal variation on the stock only. Recorded drone photos sit unaltered in square-corner cream mounts: a 9 px border with a caption rail of about 50 px, or a 9 px mat all round a wide photo. Shadows fall down and right, 8–11 px.

## Motion

Clamped smoothstep (3t² − 2t³). Cards hinge from the top or left edge over 700 ms, the face brightening from 63% to 100%. The two 0:36 flag crops lift from their real rectangles after 500 ms, travel 2.3 s on a 33 px arc and settle while the wide photo dissolves over 300 ms. Slot five: slots unfold over 380 ms with a 45 ms stagger, and the detector's empty crop and Ember's swimmer B crop hinge open in turn with still time between reveals. Reduced-motion visitors see the settled state.

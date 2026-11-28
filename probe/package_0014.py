"""Refresh the downloadable 0014 cases and the shipped crew exercise."""
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

PAGES = Path(__file__).resolve().parents[1] / "pages"
PUBLIC_SITE = "https://open-water-search.vercel.app"


def build_packet():
    online = (PAGES / "0014.html").read_text(encoding="utf-8")
    offline = online.replace('href="index.html"', f'href="{PUBLIC_SITE}/"')
    offline = offline.replace('href="first-five.html', f'href="{PUBLIC_SITE}/pages/first-five.html')
    offline = offline.replace('href="flight.html', f'href="{PUBLIC_SITE}/pages/flight.html')
    offline = offline.replace('href="history.html', f'href="{PUBLIC_SITE}/pages/history.html')
    offline = offline.replace(
        '<a class="secondary case-action" href="0014.zip" download>Download offline handoff ZIP</a>',
        "",
    )
    offline = offline.replace(
        "Extract the ZIP and open 0014.html to review both cases and try the crew exchange offline.",
        "This copy includes the two recorded cases and the simulated crew exchange. Opening the archive requires a connection.",
    )
    files = [
        "0014.css",
        "pages.css",
        "paper.css",
        "fonts/anton.woff",
        "fonts/libre-caslon-text-italic.woff",
        "art/grain.png",
        "0014-gain-frame.webp",
        "0014-gain-crop.webp",
        "0014-loss-frame.webp",
        "0014-loss-crop.webp",
        "flight/crew-reply.html",
    ]
    packet = BytesIO()
    with ZipFile(packet, "w") as bundle:
        bundle.writestr(ZipInfo("0014.html"), offline.encode("utf-8"), ZIP_DEFLATED)
        for filename in files:
            bundle.writestr(ZipInfo(filename), (PAGES / filename).read_bytes(), ZIP_DEFLATED)
    return packet.getvalue()


if __name__ == "__main__":
    (PAGES / "0014.zip").write_bytes(build_packet())

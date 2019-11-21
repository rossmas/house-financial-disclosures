import asyncio
import csv
import httpx
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime

SRC_DIR =  Path('data', 'stashed', 'year_archives')
BASE_SRC_URL = 'http://clerk.house.gov/public_disc/'
DEST_DIR = Path('data', 'stashed', 'pdfs')

# https://chrisalbon.com/python/data_wrangling/break_list_into_chunks_of_equal_size/
def chunks(_list, n):
    # For item i in a range that is a length of l,
    for i in range(0, len(_list), n):
        # Create an index range for l of n items:
        yield _list[i:i+n]

def make_dest_path(record):
    destdir = DEST_DIR.joinpath(record['Year'])
    destpath = destdir.joinpath(f"{record['DocID']}.pdf")
    return destpath

def make_error_path(record):
    destdir = DEST_DIR.joinpath('errors', record['Year'])
    destpath = destdir.joinpath(f"{record['DocID']}.txt")
    return destpath

def make_pdf_url(record):
    if record['FilingType'] == 'P':
        subdir = 'ptr-pdfs'
    else:
        subdir = 'financial-pdfs'
    subpath = f"{subdir}/{record['Year']}/{record['DocID']}.pdf"
    url = urljoin(BASE_SRC_URL, subpath, )
    return url


def gather_files(srcdir=SRC_DIR):
    return sorted(SRC_DIR.glob('*.txt'), reverse=True)

def gather_records(srcdir=SRC_DIR):
    return [row for fpath in gather_files(srcdir) for row in parse_year_file(fpath)]


def parse_year_file(srcpath):
    with open(srcpath) as o:
        data = list(csv.DictReader(o, delimiter="\t"))
        return data



async def stash(url, client, destpath, errpath):
    print("\tDownloading", url)
    resp = await client.get(url)

    if resp.status_code == 200:
        destpath.parent.mkdir(parents=True, exist_ok=True)
        destpath.write_bytes(resp.content)
        print('\tWrote', len(resp.content), 'bytes to:', destpath)
    else:
        print(f"\tError: got status code {resp.status_code} for url: {url}")
        errpath.parent.mkdir(parents=True, exist_ok=True)
        errpath.write_text(f"url: {url}\nstatus_code:{resp.status_code}\ntime:{datetime.now()}\n")

async def stash_batch(batch, _i):
    tasks = []
    async with httpx.AsyncClient() as client:
        for _j, row in enumerate(batch):
            url = make_pdf_url(row)
            destpath = make_dest_path(row)
            errpath = make_error_path(row)
            if not destpath.exists() and not errpath.exists():
                print(f"{_i}|{_j}\t{row['Year']}: {row['StateDst']} {row['Last']}, {row['First']};\t{row['DocID']}")
                t = asyncio.create_task(stash(url, client, destpath, errpath))
                tasks.append(t)

        await asyncio.gather(*tasks)

async def main():
    batches = chunks(gather_records(), 9)
    for _i, batch in enumerate(batches):
        await stash_batch(batch, _i)

if __name__ == '__main__':
    asyncio.run(main())

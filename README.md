### See also VideoInfo Plugin

* https://github.com/C5H12O5/syno-videoinfo-plugin

### GitHub

* https://github.com/oPromessa/vsMetaFileEncoder
* https://gist.github.com/soywiz/2c10feb1231e70aca19a58aca9d6c16a


### RTFM

* IMPORTANT: The .vsmeta file is available when Video Station indexes the video file first time.
* Use a Staging area to put the Videos and the .vsmeta file **outside** the Video Station Library. You can then move them inside and voila.. VideoStation reads everything nicely!
* Only support Movies .vsmeta encoding

### Setup Environment

```sh
python3.11 -m venv venv
source venv/bin/activate
pip install vsmetaEncoder
pip install imdbmovies
pip install requests
pip install click
```

```sh
python3.11 -m pip install -e .
```

### Usage
```py
Usage: imdb2vsmeta.py [OPTIONS]

  Searches on a folder for Movie Titles and generates .vsmeta and copy to
  Library.

  IMPORTANT: Use a Staging area on your NAS to generate .vsmeta and only then
  add them to you Video Library.

  It generates the temp files *.jpg and *.vsmeta on the current folder. You
  can then remove them.

Options:
  --search DIRECTORY    Folder to recursively search for media  files to be
                        processed into .vsmeta.
  --search-prefix TEXT  Media Filenames prefix for media  files to be
                        processed into .vsmeta. Eg: --search-prefix A
  -f, --force           Force copy if the destination file already exists.
  -n, --no-copy         Do not copy over the .vsmeta files.
  -v, --verbose         Shows info found on IMDB.
  --help                Show this message and exit.
```

* It generates the temp files *.jpg and *.vsmeta on the local folder. You can then remove them.

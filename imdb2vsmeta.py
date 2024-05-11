"""
    by oPromessa, 2024
    Published on https://github.com/oPromessa/imdb2vsmeta

    If you own a Synology NAS and make use of Video Station.

    And need a quick easy way to populate your Movie Library with Metadata.

    imdb2vsmeta is the answer!
"""    
import os
import shutil

import click

import re

from datetime import date, datetime
import textwrap

import requests

from imdbmovies import IMDB

# import vsmetaCodec

from vsmetaCodec.vsmetaEncoder import VsMetaMovieEncoder
from vsmetaCodec.vsmetaDecoder import VsMetaDecoder
from vsmetaCodec.vsmetaInfo import VsMetaInfo, VsMetaImageInfo


def writeVsMetaFile(filename: str, content: bytes):
    with open(filename, 'wb') as writeFile:
        writeFile.write(content)
        writeFile.close()


def readTemplateFile(filename: str) -> bytes:
    # file_content = b'\x00'
    with open(filename, 'rb') as readFile:
        file_content = readFile.read()
        readFile.close()
    return file_content


def lookfor_imdb(movie_title, year=None, tv=None):
    imdb = IMDB()
    results = imdb.search(movie_title, year=year, tv=tv)

    # Filter only movie type entries
    movie_results = [result for result in results["results"]
                     if result["type"] == "movie"]

    print(
        f"Found: [{len(movie_results)}] entries for Title: [{movie_title}] Year: [{year}]")

    for cnt, mv in enumerate(movie_results):
        print(
            f"\tEntry: [{cnt}] Name: [{click.style(mv['name'], fg='yellow')}] Id: [{mv['id']}] Type: [{mv['type']}]")

    if movie_results:
        movie_info = imdb.get_by_id(movie_results[0]['id'])
        # print(movie_info)
        return movie_results[0]['id'], movie_info
    else:
        return None, None


def search_imdb(movie_title, year):
    # imdb = IMDB()
    # year=None, tv=False,
    id, result = lookfor_imdb(movie_title, year, tv=False)

    # result = imdb.get_by_name(movie_title, tv=False)
    if id and result:
        # movie_info = imdb.get_movie(result[0].id)
        return id, result
    else:
        return None, None


def download_poster(url, filename):
    response = requests.get(url)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)


def find_metadata(title, year, filename, verbose):
    """Search for a movie/Year metada on IMDb. 
    """    
    click.echo(
        f"-------------- : Processing title [{click.style(title, fg='green')}] year [{year}] filename [{filename}]")

    vsmeta_filename = None

    year = None if year is None else int(year)

    # Search IMDB for movie information
    movie_id, movie_info = search_imdb(title, year=year)

    if movie_id and movie_info:
        # Download poster
        poster_url = movie_info['poster']
        poster_filename = f'{title.replace(" ", "_")}_poster.jpg'
        download_poster(poster_url, poster_filename)

        # Map IMDB fields to VSMETA
        # and Encode VSMETA
        vsmeta_filename = filename + ".vsmeta"
        map_to_vsmeta(movie_id, movie_info, poster_filename,
                      vsmeta_filename, verbose)
    else:
        print(f"No information found for '{click.style(title, fg='red')}'")

    click.echo(
        f"\tProcessed title [{click.style(title, fg='green')}] year [{year}] vsmeta [{vsmeta_filename}]")

    return vsmeta_filename


def map_to_vsmeta(imdb_id, imdb_info, posterFile, vsmeta_filename, verbose):

    # vsmetaMovieEncoder
    vsmeta_writer = VsMetaMovieEncoder()

    # Build up vsmeta info
    info = vsmeta_writer.info

    # Title
    info.showTitle = imdb_info['name']
    info.showTitle2 = imdb_info['name']
    # Tag line
    info.episodeTitle = f"{imdb_info['name']}"

    # Publishing Date - episodeReleaseDate
    # also sets Year
    # info.year=imdb_info['datePublished'][:4]
    info.setEpisodeDate(date(
        int(imdb_info['datePublished'][:4]),
        int(imdb_info['datePublished'][5:7]),
        int(imdb_info['datePublished'][8:])))

    # Set to 0 for Movies: season and episode
    info.season = 0
    info.episode = 0

    # Not used. Set to 1900-01-01
    info.tvshowReleaseDate = date(1900, 1, 1)

    # Try with Locked = False
    info.episodeLocked = False

    # Double check!
    info.timestamp = int(datetime.now().timestamp())

    # Classification
    # A rating of None would crash the reading of .vsmeta file with error:
    #    return info._readData(info.readSpecialInt()).decode()
    #           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    # UnicodeDecodeError: 'utf-8' codec can't decode byte 0x8a in position 1: invalid start byte
    info.classification = "" if imdb_info['contentRating'] is None else imdb_info['contentRating']

    # Rating
    info.rating = imdb_info['rating']['ratingValue']

    # Summary
    info.chapterSummary = imdb_info['description']

    # Cast
    info.list.cast = []
    for actor in imdb_info['actor']:
        info.list.cast.append(actor['name'])

    # Director
    info.list.director = []
    for director in imdb_info['director']:
        info.list.director.append(director['name'])

    # Writer
    info.list.writer = []
    for creator in imdb_info['creator']:
        info.list.writer.append(creator['name'])

    # Genre
    info.list.genre = imdb_info['genre']

    # Read JPG images for Poster and Background
    with open(posterFile, "rb") as image:
        f = image.read()

    # Poster (of Movie)
    episode_img = VsMetaImageInfo()
    episode_img.image = f
    info.episodeImageInfo.append(episode_img)

    # Background (of Movie)
    # Use Posters file for Backdrop also
    info.backdropImageInfo.image = f

    # Not used. Set to VsImageIfnfo()
    info.posterImageInfo = episode_img

    if verbose:
        click.echo(f"\t---------------: ---------------")
        click.echo(f"\tIMDB id        : {imdb_id}")
        click.echo(f"\tTitle          : {info.showTitle}")
        click.echo(f"\tTitle2         : {info.showTitle2}")
        click.echo(f"\tEpisode title  : {info.episodeTitle}")
        click.echo(f"\tEpisode year   : {info.year}")
        click.echo(f"\tEpisode date   : {info.episodeReleaseDate}")
        click.echo(f"\tEpisode locked : {info.episodeLocked}")
        click.echo(f"\tTimeStamp      : {info.timestamp}")
        click.echo(f"\tClassification : {info.classification}")
        click.echo(f"\tRating         : {info.rating:1.1f}")
        wrap_text = "\n\t                 ".join(
            textwrap.wrap(info.chapterSummary, 150))
        click.echo("\tSummary        : {0}".format(wrap_text))
        click.echo(f"\tCast           : " +
                   "".join(["{0}, ".format(name) for name in info.list.cast]))
        click.echo(f"\tDirector       : " +
                   "".join(["{0}, ".format(name) for name in info.list.director]))
        click.echo(f"\tWriter         : " +
                   "".join(["{0}, ".format(name) for name in info.list.writer]))
        click.echo(f"\tGenre          : " +
                   "".join(["{0}, ".format(name) for name in info.list.genre]))
        click.echo(f"\t---------------: ---------------")

    writeVsMetaFile(vsmeta_filename, vsmeta_writer.encode(info))

    return True


def copy_file(source, destination, force=False, no_copy=False, verbose=False):
    """Copy a source file to destination. 
    
    Dry-run (no_copy), Force overwrite and Verbose options. 
    """    

    if verbose:
        click.echo(f"\tCopying title [{source}] to [{destination}]")

    # Check if the source file exists
    if os.path.isfile(source):
        # Extract the file name from the source file path
        file_name = os.path.basename(source)

        if not no_copy:
            # Copy the file to the destination folder if it doesn't exist there
            if not os.path.exists(destination):
                shutil.copy(source, destination)
                print(
                    f"\tCopied ['{file_name}'] to ['{destination}'].")
            elif not force:
                click.echo(
                    f"\tSkipping ['{file_name}'] in ['{destination}']. Destination exists. See -f option.")
            else:
                click.echo(
                    f"\tOverwriting ['{file_name}'] in ['{destination}'].")
                shutil.copy(source, destination)
                print(
                    f"\tCopied ['{file_name}'] to ['{destination}'].")
        else:
            click.echo(
                f"\tNo copy: ['{file_name}'] in ['{destination}'].")

    else:
        print(f"\tNot found source file []'{source}'].")


def find_files(root_dir, filename_prefix, valid_ext=(".mp4", ".mkv", ".avi", ".mpg")):

    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.startswith(filename_prefix) and \
               any(file.casefold().endswith(ext) for ext in valid_ext) and \
               not os.path.isdir(os.path.join(root, file)):
                yield os.path.join(root, file)


def extract_info(file_path):
    dirname = os.path.dirname(file_path)
    basename = os.path.basename(file_path)

    # filtered_value = re.search(r'\D*(\d{4})', basename)
    filtered_value = re.search(r'^(.*?)(\d{4})(.*)$', basename)
    filtered_title = None
    filtered_year = None
    if filtered_value:
        filtered_title = filtered_value.group(1)
        filtered_year = filtered_value.group(2)
    else:
        filtered_title = basename

    filtered_title = filtered_title.replace('.', ' ').strip()

    return dirname, basename, filtered_title, filtered_year


def check_file(file_path):
    """Read .vsmeta file and print it's contents. 

    Images within .vsmeta are saved as image_back_drop.jpg and image_poster_NN.jpg
    When checking multiple files, these files are overwritten.
    """

    vsmeta_bytes = readTemplateFile(file_path)
    reader = VsMetaDecoder()
    reader.decode(vsmeta_bytes)

    if reader.info.season == 0:
        vsmeta_type = "movie"
    else:
        vsmeta_type = "series"
        if reader.info.tvshowMetaJson == "null":
            reader.info.tvshowMetaJson = ""

    reader.info.printInfo('.', prefix=os.path.basename(file_path))


@click.command()
@click.option('--search', type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
              help="Folder to recursively search for media  files to be processed into .vsmeta.")
@click.option('--search-prefix', type=click.STRING, default="",
              help="Media Filenames prefix for media  files to be processed into .vsmeta. Eg: --search-prefix A")
@click.option("--check", type=click.Path(exists=True, file_okay=True, dir_okay=True, resolve_path=True),
              help="Check .vsmeta files. Show info. Exclusive with --search option.")
@click.option('-f', '--force', is_flag=True, help="Force copy if the destination file already exists.")
@click.option('-n', '--no-copy', is_flag=True, help="Do not copy over the .vsmeta files.")
@click.option('-v', '--verbose', is_flag=True, help="Shows info found on IMDB.")
def main(search, search_prefix, force, no_copy, verbose, check):
    """Searches on a folder for Movie Titles and generates .vsmeta and copy to Library.

       IMPORTANT: Use a Staging area on your NAS to generate .vsmeta and only then add them to you Video Library.

       It generates the temp files *.jpg and *.vsmeta on the current folder. You can then remove them.
    """

    if not (check or search):
        raise click.UsageError(
            "Must specify at least one option --search or --check. Use --help for additional help.")

    if check and (search or force or no_copy):
        raise click.UsageError(
            "Option --check is incompatible with --search, --force and --no-copy options.")

    if force and no_copy:
        raise click.UsageError(
            "Options --force and --no-copy are exclusive, please provide only one.")

    if check:
        if os.path.isfile(check) and check.endswith(".vsmeta"):
            click.echo(f"-------------- : Checking file [{check}]")
            check_file(check)
        elif os.path.isdir(check):
            for found_file in find_files(check, search_prefix, valid_ext=('.vsmeta', )):
                click.echo(f"-------------- : Checking file [{check}]")
                check_file(found_file)
        else:
            raise click.UsageError(
                "Invalid check path or file name. Please provide a valid directory or .vsmeta file.")

    if search:
        click.echo(f"Processing folder: [{search}].")
        # Set the root directory and filename prefix
        root_dir = '/Volumes/video/Movies/'
        filename_prefix = 'A'

        # Iterate over the matching files
        for found_file in find_files(search, search_prefix):
            # click.echo(f"Found file: [{found_file}]")
            dirname, basename, title, year = extract_info(found_file)
            vsmeta = find_metadata(title, year, basename, verbose)
            if vsmeta:
                copy_file(vsmeta, os.path.join(dirname, vsmeta),
                          force, no_copy, verbose)


if __name__ == "__main__":
    main()

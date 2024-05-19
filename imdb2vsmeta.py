"""
    by oPromessa, 2024
    Published on https://github.com/oPromessa/imdb2vsmeta

    If you own a Synology NAS and make use of Video Station.

    And need a quick easy way to populate your Movie Library with Metadata.

    imdb2vsmeta is the answer!
"""
import os
import re
import shutil

from datetime import date, datetime
import textwrap

import click
import requests

from imdbmovies import IMDB

from vsmetaCodec.vsmetaEncoder import VsMetaMovieEncoder, VsMetaSeriesEncoder
from vsmetaCodec.vsmetaDecoder import VsMetaDecoder
from vsmetaCodec.vsmetaInfo import VsMetaImageInfo


class MutuallyExclusiveOption(click.Option):
    """ click class to check mutually exclusive options.
    """

    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        help_text = kwargs.get('help', '')
        if self.mutually_exclusive:
            ex_str = ', '.join(self.mutually_exclusive)
            kwargs['help'] = help_text + (
                ' NOTE: This argument is mutually exclusive with'
                ' arguments: [' + ex_str + '].'
            )
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                f"Illegal usage: `{self.name}` is mutually exclusive with "
                f"arguments `{', '.join(self.mutually_exclusive)}`.")

        return super().handle_parse_result(
            ctx, opts, args
        )


def write_vsmeta_file(filename: str, content: bytes):
    """ Writes to file in binary mode. Used to write .vsmeta files.
    """
    with open(filename, 'wb') as write_file:
        write_file.write(content)
        write_file.close()


def read_vsmeta_file(filename: str) -> bytes:
    """ Reads from file in binary mode. Used to read .vsmeta files.
    """
    with open(filename, 'rb') as read_file:
        file_content = read_file.read()
        read_file.close()
    return file_content


def lookfor_imdb(movie_title, year=None, tv=False):
    """ Returns movie_info of first movie/tv series from year 
        returned by search in IMDb.
    """
    imdb = IMDB()
    results = imdb.search(movie_title, year=year, tv=tv)

    # Filter only movie type entries
    movie_results = [result for result in results["results"]
                     if result["type"] == ("tvSeries" if tv else "movie")]

    print(
        f"Found: [{len(movie_results)}] entries for "
        f"Title: [{movie_title}] Year: [{year}]"
    )

    for cnt, mv in enumerate(movie_results):
        print(
            f"\tEntry: [{cnt}] Name: [{click.style(mv['name'], fg='yellow')}] "
            f"Id: [{mv['id']}] Type: [{mv['type']}]"
        )

    if movie_results:
        movie_info = imdb.get_by_id(movie_results[0]['id'])
        return movie_results[0]['id'], movie_info

    return None, None


def download_poster(url, filename):
    """ Download image poster (returned by IMDb) from URL info JPG filename.
    """
    # Set HTTP requests timeoout
    http_timeout = 15

    try:
        response = requests.get(url, timeout=http_timeout)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("Http Error:", e)
    except requests.exceptions.ConnectionError as e:
        print("Error Connecting:", e)
    except requests.exceptions.Timeout as e:
        print("Timeout Error:", e)
    except requests.exceptions.RequestException as e:
        print("OOps: Something Else", e)

    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)


def find_metadata(title, year, filename, verbose, 
                  tv=False, season = 0, episode = 0):
    """Search for a movie/Year metada on IMDb.

       If found, downloads to a local .JPG file the poster
    """
    click.echo(
        f"-------------- : Processing title [{click.style(title, fg='green')}] "
        f"year [{year}] filename [{filename}]")

    vsmeta_filename = None

    year = None if year is None else int(year)

    # Search IMDB for movie information
    movie_id, movie_info = lookfor_imdb(title, year=year, tv=tv)

    if movie_id and movie_info:
        # Download poster
        poster_url = movie_info['poster']
        poster_filename = f'{title.replace(" ", "_")}_poster.jpg'
        download_poster(poster_url, poster_filename)

        # Map IMDB fields to VSMETA
        # and Encode VSMETA
        vsmeta_filename = filename + ".vsmeta"
        map_to_vsmeta(movie_id, movie_info, poster_filename,
                      vsmeta_filename, tv, season, episode, verbose)
    else:
        print(f"No information found for '{click.style(title, fg='red')}'")

    click.echo(
        f"\tProcessed title [{click.style(title, fg='green')}] "
        f"year [{year}] vsmeta [{vsmeta_filename}]")

    return vsmeta_filename


def map_to_vsmeta(imdb_id, imdb_info,
                  poster_file, vsmeta_filename,
                  tv, season, episode,
                  verbose):
    """Encodes a .VSMETA file based on imdb_info and poster_file """
    if tv:
        map_to_vsmeta_series(imdb_id, imdb_info, season, episode, poster_file,
                             vsmeta_filename, verbose)
    else:
        map_to_vsmeta_movie(imdb_id, imdb_info, poster_file,
                            vsmeta_filename, verbose)


def map_to_vsmeta_movie(imdb_id, imdb_info, poster_file, vsmeta_filename, verbose):
    """Encodes a .VSMETA Movie file based on imdb_info and poster_file """

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

    # Locked = False. If True, in Video Sation does not allow changes to vsmeta.
    info.episodeLocked = False

    info.timestamp = int(datetime.now().timestamp())

    # Classification
    # A classification of None would crash the reading of .vsmeta file.
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
    if os.path.isfile(poster_file):
        with open(poster_file, "rb") as image:
            f = image.read()

        # Poster (of Movie)
        if f is not None:
            episode_img = VsMetaImageInfo()
            episode_img.image = f
            info.episodeImageInfo.append(episode_img)

            # Background (of Movie)
            # Use Posters file for Backdrop also
            info.backdropImageInfo.image = f

            # Not used. Set to VsImageIfnfo()
            info.posterImageInfo = episode_img

    if verbose:
        click.echo("\t---------------: ---------------")
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
            textwrap.wrap(info.chapterSummary, 80))
        click.echo(f"\tSummary        : {wrap_text}")
        click.echo(
            f"\tCast           : {''.join([f'{name}, ' for name in info.list.cast])}")
        click.echo(
            f"\tDirector       : {''.join([f'{name}, ' for name in info.list.director])}")
        click.echo(
            f"\tWriter         : {''.join([f'{name}, ' for name in info.list.writer])}")
        click.echo(
            f"\tGenre          : {''.join([f'{name}, ' for name in info.list.genre])}")
        click.echo("\t---------------: ---------------")

    write_vsmeta_file(vsmeta_filename, vsmeta_writer.encode(info))


def map_to_vsmeta_series(imdb_id, imdb_info, season, episode, 
                         poster_file, vsmeta_filename, verbose):
    """Encodes a .VSMETA Series file based on imdb_info and poster_file """

    vsmeta_writer = VsMetaSeriesEncoder()

    # Build up vsmeta info
    info = vsmeta_writer.info

    # Title
    info.showTitle = imdb_info['name']
    # info.showTitle2 = imdb_info['name']
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
    info.season = season
    info.episode = episode

    info.tvshowReleaseDate = date(
        int(imdb_info['datePublished'][:4]),
        int(imdb_info['datePublished'][5:7]),
        int(imdb_info['datePublished'][8:]))

    # Locked = False. If True, in Video Sation does not allow changes to vsmeta.
    info.episodeLocked = False

    info.timestamp = int(datetime.now().timestamp())

    # Classification
    # A classification of None would crash the reading of .vsmeta file.
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
    # info.list.genre = imdb_info['genre']

    # Read JPG images for Poster and Background
    if os.path.isfile(poster_file):
        with open(poster_file, "rb") as image:
            f = image.read()

        # Poster (of Movie)
        if f is not None:
            episode_img = VsMetaImageInfo()
            episode_img.image = f
            info.episodeImageInfo.append(episode_img)

            # Background (of Movie)
            # Use Posters file for Backdrop also
            info.backdropImageInfo.image = f

            # Not used. Set to VsImageIfnfo()
            info.posterImageInfo = episode_img

    if verbose:
        click.echo("\t---------------: ---------------")
        click.echo(f"\tIMDB id        : {imdb_id}")
        click.echo(f"\tTitle          : {info.showTitle}")
        click.echo(f"\tTitle2         : {info.showTitle2}")
        click.echo(f"\tEpisode title  : {info.episodeTitle}")
        click.echo(f"\tEpisode year   : {info.year}")
        click.echo(f"\tEpisode date   : {info.episodeReleaseDate}")
        click.echo(f"\tTV Show date   : {info.tvshowReleaseDate}")
        click.echo(f"\tTV Show Season : {info.season}")
        click.echo(f"\tTV Show Episode: {info.episode}")

        click.echo(f"\tEpisode locked : {info.episodeLocked}")
        click.echo(f"\tTimeStamp      : {info.timestamp}")
        click.echo(f"\tClassification : {info.classification}")
        click.echo(f"\tRating         : {info.rating:1.1f}")
        wrap_text = "\n\t                 ".join(
            textwrap.wrap(info.chapterSummary, 80))
        click.echo(f"\tSummary        : {wrap_text}")
        click.echo(
            f"\tCast           : {''.join([f'{name}, ' for name in info.list.cast])}")
        click.echo(
            f"\tDirector       : {''.join([f'{name}, ' for name in info.list.director])}")
        click.echo(
            f"\tWriter         : {''.join([f'{name}, ' for name in info.list.writer])}")
        click.echo(
            f"\tGenre          : {''.join([f'{name}, ' for name in info.list.genre])}")
        click.echo("\t---------------: ---------------")

    write_vsmeta_file(vsmeta_filename, vsmeta_writer.encode(info))


def copy_file(source, destination, force=False, no_copy=False, verbose=False):
    """Copy a source file to destination.

    Dry-run (no_copy), Force overwrite and Verbose options.
    """

    if verbose:
        click.echo(f"\tCopying title ['{source}'] to ['{destination}']")

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
                    f"\tSkipping ['{file_name}'] in ['{destination}']. "
                    "Destination exists. See -f option.")
            else:
                try:
                    click.echo(
                        f"\tOverwriting ['{file_name}'] in ['{destination}'].")
                    shutil.copy(source, destination)
                    print(
                        f"\tCopied ['{file_name}'] to ['{destination}'].")
                except shutil.SameFileError as e:
                    print(
                        f"\tNot overwriting same file ['{file_name}'] "
                        f"error ['{e}'].")
        else:
            click.echo(
                f"\tNo copy: ['{file_name}'] in ['{destination}'].")

    else:
        print(f"\tNot found source file []'{source}'].")


def find_files(
    root_dir,
    filename_prefix,
    valid_ext=(
        ".mp4",
        ".mkv",
        ".avi",
        ".mpg")):
    """ Returns files with extension in valid_ext list
    """

    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.startswith(filename_prefix) and \
               any(file.casefold().endswith(ext) for ext in valid_ext) and \
               not os.path.isdir(os.path.join(root, file)):
                yield os.path.join(root, file)


def extract_info(file_path, tv):
    """ Convert file_path into dirname and from basename extract
        movie_tile and year. Expecting filename format 'movie title name (1999)'
    """
    dirname = os.path.dirname(file_path)
    basename = os.path.basename(file_path)

    # filtered_value = re.search(r'\D*(\d{4})', basename)
    if tv:
        filtered_value = re.search(r'^(.*?)(\d{4})(.*)$',
                                   basename)
    else:
        filtered_value = re.search(r'^(.*?)(\d{4})(.*)([sS]\d{2}[sE]\d{2})(.*)$',
                                   basename)

    filtered_title = None
    filtered_year = None
    filtered_season = None
    filtered_episode = None

    if filtered_value:
        filtered_title = filtered_value.group(1)
        filtered_year = filtered_value.group(2)
        if tv:
            filtered_season = int(filtered_value.group(3)[2:4])
            filtered_episode = int(filtered_value.group(3)[5:7])

    else:
        filtered_title = basename

    filtered_title = filtered_title.replace('.', ' ').strip()

    return dirname, basename, filtered_title, filtered_year, filtered_season, filtered_episode


def check_file(file_path):
    """Read .vsmeta file and print it's contents.

    Images within .vsmeta are saved as image_back_drop.jpg and image_poster_NN.jpg
    When checking multiple files, these files are overwritten.
    """

    vsmeta_bytes = read_vsmeta_file(file_path)
    reader = VsMetaDecoder()
    reader.decode(vsmeta_bytes)

    # IF vsmeta file is a Movie
    if reader.info.season == 0:
        reader.info.printInfo('.', prefix=os.path.basename(file_path))


@click.command()
@click.option('--movies', is_flag=True,
              cls=MutuallyExclusiveOption, mutually_exclusive=['series'],
              help='Specify if it is a movie. Must choose movies or series.')
@click.option('--series', is_flag=True,
              cls=MutuallyExclusiveOption, mutually_exclusive=['movies'],
              help='Specify if it is a series. Must choose movies or series.')
@click.option('--search',
              type=click.Path(exists=True,
                              file_okay=False,
                              dir_okay=True,
                              resolve_path=True),
              cls=MutuallyExclusiveOption, mutually_exclusive=['check'],
              help="Folder to recursively search for media  files to be "
                   "processed into .vsmeta.")
@click.option("--check",
              type=click.Path(exists=True,
                              file_okay=True,
                              dir_okay=True,
                              resolve_path=True),
              cls=MutuallyExclusiveOption, mutually_exclusive=['search'],
              help="Check .vsmeta files. Show info. "
                   "Exclusive with --search option.")
@click.option('--search-prefix', type=click.STRING, default="",
              help="Media Filenames prefix for media  files to be processed "
                   "into .vsmeta. Eg: --search-prefix A")
@click.option('-f', '--force', is_flag=True,
              cls=MutuallyExclusiveOption, mutually_exclusive=['no_copy'],
              help="Force copy if the destination file already exists.")
@click.option('-n', '--no-copy', is_flag=True,
              help="Do not copy over the .vsmeta files.")
@click.option('-v', '--verbose', is_flag=True, help="Shows info found on IMDB.")
def cli(movies, series, search, search_prefix, check, force, no_copy, verbose):
    """Searches on a folder for Movie Titles and generates .vsmeta file and
       copies them over to your Video Station Library

       IMPORTANT: Use a Staging area on your NAS to generate .vsmeta and only
                  then, add them to you Video Library.

       It generates the temp files *.jpg and *.vsmeta on the current folder. 
       You can then remove them.
    """

    if movies:
        click.echo('Movies selected.')
    elif series:
        click.echo('Series selected.')
    else:
        raise click.UsageError(
            'Neither movie nor series selected.')

    if not (check or search):
        raise click.UsageError(
            "Must specify at least one option --search or --check. "
            "Use --help for additional help.")

    if check and (search or force or no_copy):
        raise click.UsageError(
            "Option --check is incompatible with --search, --force "
            "and --no-copy options.")

    if check:
        if os.path.isfile(check) and check.endswith(".vsmeta"):
            click.echo(f"-------------- : Checking file [{check}]")
            check_file(check)
        elif os.path.isdir(check):
            for found_file in find_files(
                    check,
                    search_prefix,
                    valid_ext=(
                        '.vsmeta',
                    )):
                click.echo(f"-------------- : Checking file [{check}]")
                check_file(found_file)
        else:
            raise click.UsageError(
                "Invalid check path or file name. "
                "Please provide a valid directory or .vsmeta file.")

    if search:
        click.echo(f"Processing folder: [{search}].")

        # Iterate over the matching files
        for found_file in find_files(search, search_prefix):
            # click.echo(f"Found file: [{found_file}]")
            dirname, basename, title, year, season, episode = extract_info(
                found_file, False if movies else True)
            if movies:
                vsmeta = find_metadata(
                    title, year, basename, verbose, tv=False)
            elif series:
                vsmeta = find_metadata(
                    title, year, basename, verbose, tv=True, 
                    season=season, episode=episode)
            if vsmeta:
                copy_file(vsmeta, os.path.join(dirname, vsmeta),
                          force, no_copy, verbose)


if __name__ == "__main__":
    # pylint: disable = no-value-for-parameter
    cli()

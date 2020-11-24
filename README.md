# DjVu RLE Image Plugin, for Pillow
This is a simple decoder for the DjVu RLE image format as defined in the ([DjVuLibre docs](http://djvu.sourceforge.net/doc/man/csepdjvu.html)).

## Usage
Simply place DjvuRleImagePlugin.py in your working folder and do `import DjvuRleImagePlugin`. You should now be able to use PIL to open DjVu RLE files: `im = Image.open("Image.rle")`.

## Current status
BETA! I have tested it with some bitonal images generated with the DjVuLibre decoder:
    `ddjvu -format=rle out.djvu test.djvurle`
Unfortunately, there is no way to generate color RLE files with the DjVuLibre tools. So I have built some synthetic testing files which also seem to work.

## Future work
- Write some tests.
- Write an encoder.

## License
The plugin was written following PIL's [PpmImagePlugin](https://github.com/python-pillow/Pillow/blob/master/src/PIL/PpmImagePlugin.py), [DdsImagePlugin](https://github.com/python-pillow/Pillow/blob/master/docs/example/DdsImagePlugin.py), [SgiImagePlugin](https://pillow.readthedocs.io/en/stable/_modules/PIL/SgiImagePlugin.html) and [MspImagePlugin](https://pillow.readthedocs.io/en/stable/_modules/PIL/MspImagePlugin.html) source code files, so I have used the same HPND License.

## Alternatives
There are only a couple alternatives I know of:
- [`pbmtodjvurle`](http://netpbm.sourceforge.net/doc/pbmtodjvurle.html) and [`pamtodjvurle`](http://netpbm.sourceforge.net/doc/pamtodjvurle.html) from the [Netpbm](http://netpbm.sourceforge.net/) toolkit. However, these only encode from PBM/PAM to DjVu RLE, and not vice versa. Also, no up to date binaries for Windows are available.
- `ddjvu`, the DjVuLibre DjVu decoder. It can only produce _bitonal_ DjVu RLE files from each of the available layers of a djvu input file.

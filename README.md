# DjVu RLE Image Plugin, for PIL
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
The plugin was written following PIL's [PpmImagePlugin](https://github.com/python-pillow/Pillow/blob/master/src/PIL/PpmImagePlugin.py) source code, so I decided to use the same HPND License.

# DJVU RLE image format

This specification has been taken from the DjVuLibre documentation ([CSEPDJVU](http://djvu.sourceforge.net/doc/man/csepdjvu.html "CSEPDJVU")).

## Bitonal RLE format
The Bitonal RLE format is a simple run-length encoding scheme for bitonal images. The data always begin with a text header composed of the two characters "R4", the number of columns, and the number of rows. All numbers are expressed in decimal ASCII. These three items are separated by blank characters (space, tab, carriage return, or linefeed) or by comment lines introduced by character "#". The last number is followed by exactly one character which usually is a linefeed character.

The rest of the file encodes a sequence of numbers representing the lengths of alternating runs of transparent and black pixels. Lines are encoded starting with the top line and progressing toward the bottom line. Each line starts with a white run. The decoder knows that a line is finished when the sum of the run lengths for that line is equal to the number of columns in the image. Numbers in range 0 to 191 are represented by a single byte in range 0x00 to 0xBF. Numbers in range 192 to 16383 are represented by a two byte sequence: the first byte, in range 0xc0 to 0xFF, encodes the six most significant bits of the number, the second byte encodes the remaining eight bits of the number. This scheme allows for runs of length zero, which are useful when a line starts with a black pixel, and when a very long run (whose length exceeds 16383) must be split into smaller runs.

## Color RLE format
The Color RLE format is a simple run-length encoding scheme for color images with a limited number of distinct colors. The data always begin with a text header composed of the two characters "R6", the number of columns, the number of rows, and the number of color palette entries. All numbers are expressed in decimal ASCII. These four items are separated by blank characters (space, tab, carriage return, or linefeed) or by comment lines introduced by character "#". The last number is followed by exactly one character which usually is a linefeed character.

The header is followed by the color palette containing three bytes per color entry. The bytes represent the red, green, and blue components of the color.

The palette is followed by a collection of four bytes integers (most significant bit first) representing runs of pixels with an identical color. The twelve upper bits of this integer indicate the index of the run color in the palette entry. The twenty lower bits of the integer indicate the run length. Color indices greater than 0xFF0 are reserved. Color index 0xFFF is used for transparent runs. Each row is represented by a sequence of runs whose lengths add up to the image width. Rows are encoded starting with the top row and progressing toward the bottom row.

# Implementation details:
Having such a succinct specification leaves some details open to interpretation. Following the [Netpbm formats](http://netpbm.sourceforge.net/doc/#formats) specifications, this implementation makes the following assumptions:
- Assumes comment lines start with "#" and end with "LF" or "CR".
- Assumes comment lines can start in the middle of an item.
- Since both formats state that "the last number is followed by exactly one character which _usually_ is a linefeed character", assumes _that_ last character is always a whitespace.
- Assumes the color RLE format also allows runs of length zero.

# Complementary specifications

The following complementary definitions can be found in the DjVuLibre source code files ([GBitmap.h](https://sourceforge.net/p/djvu/djvulibre-git/ci/master/tree/libdjvu/GBitmap.h), [csepdjvu.cpp](https://sourceforge.net/p/djvu/djvulibre-git/ci/master/tree/tools/csepdjvu.cpp)). They basically state the same, and are included here for reference.

## RLE
The binary RLE file format is a simple run-length encoding scheme for storing bilevel images. Encoding or decoding a RLE encoded file is extremely simple. Yet RLE encoded files are usually much smaller than the corresponding PBM encoded files. RLE files always begin with a header line composed of:
- the two characters "R4",
- one or more blank characters,
- the number of columns, encoded using characters "0" to "9",
- one or more blank characters,
- the number of lines, encoded using characters "0" to "9",
- exactly one blank character (usually a line-feed character).

The rest of the file encodes a sequence of numbers representing the lengths of alternating runs of white and black pixels. Lines are encoded starting with the top line and progressing towards the bottom line. Each line starts with a white run. The decoder knows that a line is finished when the sum of the run lengths for that line is equal to the number of columns in the image. Numbers in range 0 to 191 are represented by a single byte in range 0x00 to 0xbf. Numbers in range 192 to 16383 are represented by a two byte sequence: the first byte, in range 0xc0 to 0xff, encodes the six most significant bits of the number, the second byte encodes the remaining eight bits of the number. This scheme allows for runs of length zero, which are useful when a line starts with a black pixel, and when a very long run (whose length exceeds 16383) must be split into smaller runs.

## Color RLE Images

The Color RLE file format is a simple run-length encoding scheme for color images with a limited number of colors. Color RLE files always begin with a text header composed of:
- the two characters "R6",
- the number of columns in decimal,
- the number of rows in decimal,
- the number of palette entries in decimal.
These four items are separated by blank characters (space, tab, cr, or nl) or by comment lines introduced by character "#". The last number is followed by exactly one character (usually a nl character). This header is followed by a palette containing three bytes per color. The bytes represent the red, green, and blue components of the color.

The palette is followed by four bytes integers (MSB first) representing runs. The twelve upper bits of this integer indicate the index of the run color in the palette entry. The twenty lower bits of the integer indicate the run length. Color indices greater than 0xff0 are reserved for pixels belonging to the background layer. Color index 0xfff is used for transparent runs. Color index 0xffe is used for don't-care runs (i.e. pixels whose values should be taken by smoothly completing the background using the wavelet masking algorithm). Each row is represented by a sequence of runs whose lengths add up to the image width. Rows are encoded starting with the top row and progressing towards the bottom row.

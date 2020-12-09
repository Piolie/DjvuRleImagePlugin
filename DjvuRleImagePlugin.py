#
# The Python Imaging Library.
# $Id$
#
# DjVu RLE support for Pillow
#
# History:
#       2020-11-18     Created; decoder implemented.
#       2020-12-05     Encoder implemented
#
# Copyright (c) Piolie.
#
# See the README file for information on usage and redistribution.
#

"""
A Pillow plugin to decode and encode DjVu RLE images
as specified in the DjVuLibre docs.
"""

# from io import BytesIO
from PIL import Image, ImageFile

#
# --------------------------------------------------------------------

WHITESPACE = b" \t\r\n"  # whitespace can be: space, tab, CR, or LF

MODES = {  # image modes for the two formats
    b"R4": "1",  # bitonal
    b"R6": "RGBA",  # paletted with transparency
}


def _accept(prefix):
    return prefix[0:1] == b"R" and prefix[1] in b"46"


class DjvuRleImageFile(ImageFile.ImageFile):
    """
    Class to identify DjVu RLE files.
    """

    format = "DJVURLE"
    format_description = "DjVu RLE image"

    def _read_token(self, s=b""):
        """
        Read one token and detect errors in format.
        """

        def _is_decimal_ascii(c):  # verifies ASCII decimal
            return b"\x2F" < c < b"\x3A"

        def _ignore_line():  # ignores line; line ends with CR _xor_ LF
            while True:
                c = self.fp.read(1)
                if c == b"":  # reached EOF
                    raise EOFError("Reached EOF while reading header")
                if c in b"\r\n":
                    break

        while True:  # read until non-whitespace is found
            c = self.fp.read(1)
            if c == b"":  # reached EOF
                raise EOFError("Reached EOF while reading header")
            if _is_decimal_ascii(c):  # found what we were looking for
                break
            if c == b"#":  # found comment line, ignore it
                _ignore_line()
                continue
            if c in WHITESPACE:  # found whitespace, ignore it
                continue
            raise ValueError("Non-decimal-ASCII found in header")

        s = s + c

        while True:  # read until next whitespace
            c = self.fp.read(1)
            if _is_decimal_ascii(c):  # append decimal
                s = s + c
                continue
            if c in WHITESPACE:  # token ended
                break
            if c == b"#":
                _ignore_line()
                continue
            else:
                raise ValueError("Non-decimal-ASCII found in header")

        return s

    def _open(self):
        """
        Load image parameters.
        """
        # read magic number
        s = self.fp.read(1)
        if s != b"R":  # TODO: redundant? (already have _accept)
            raise ValueError("Not a DJVURLE file")
        magic_number = self._read_token(s)
        self.mode = MODES[magic_number]

        self.custom_mimetype = {
            b"R4": "image/x-djvurle-bitmap",
            b"R6": "image/x-djvurle-pixmap",
        }[magic_number]

        for ix in range(3):
            token = int(self._read_token())
            if ix == 0:  # token is the x size
                xsize = token
            elif ix == 1:  # token is the y size
                ysize = token
                if self.mode == "1":
                    number_of_colors = 0  # bitonal decoder ignores this value
                    break
            elif ix == 2:  # token is the number of colors
                if token > 4080:  # check palette size
                    raise ValueError(
                        f"Too many colors: {token}; reduce to 4080 or less"
                    )
                number_of_colors = token

        self._size = xsize, ysize
        self.tile = [
            (
                "DJVURLE",  # decoder
                (0, 0) + self._size,  # region: whole image
                self.fp.tell(),  # offset to image data
                number_of_colors,  # parameters for decoder
            )
        ]


class DjvuRleDecoder(ImageFile.PyDecoder):
    """
    Class to decode DjVu RLE images.
    """

    _pulls_fd = True  # TODO: experimental; gotta learn how to do it with buffer

    def decode(self, buffer):
        xsize = self.state.xsize  # row length
        ysize = self.state.ysize  # number of rows
        size = xsize * ysize  # total number of pixels
        # if using buffer;
        # TODO: not sure about the performance impact of wrapping in BytesIO...
        # buffer = BytesIO(buffer)
        buffer = self.fd  # if using _pulls_fd

        def decode_bitonal():
            BITONAL_MASK = 0x3FFF
            decoded_data = bytearray()  # much faster than: data = bytes()

            total_length = 0
            while total_length < size:
                is_white_run = True  # each line starts with a white run
                line_length = 0
                while line_length < xsize:
                    first_byte = buffer.read(1)
                    if first_byte == b"":
                        raise EOFError("Reached EOF while reading image data")
                    if first_byte > b"\xBF":  # two-byte run
                        second_byte = buffer.read(1)
                        if second_byte == b"":
                            raise EOFError("Reached EOF while reading image data")
                        run_length = (
                            int.from_bytes(first_byte + second_byte, byteorder="big")
                            & BITONAL_MASK  # make the two MSBs zero
                        )
                    else:
                        run_length = ord(first_byte)

                    line_length += run_length
                    if line_length > xsize:  # check line length
                        raise ValueError(
                            f"Run too long in line: {total_length//xsize + 1}"
                        )
                    decoded_data += (b"\xFF" * is_white_run or b"\x00") * run_length
                    is_white_run = not is_white_run
                total_length += line_length
            if buffer.read() != b"":
                raise EOFError("There are extra data at the end of the file")
            self.set_as_raw(bytes(decoded_data), rawmode="1;8")

        def decode_rgba():
            COLOR_MASK = 0xFFFFF
            decoded_data = bytearray()

            number_of_colors = self.args[0]
            palette = {}
            for n in range(number_of_colors):  # load colors in palette
                color = buffer.read(3)
                if len(color) < 3:
                    raise EOFError("Reached EOF while reading image palette")
                palette[n] = color
            total_length = 0
            while total_length < size:
                line_length = 0
                while line_length < xsize:
                    raw_run = buffer.read(4)
                    if len(raw_run) < 4:
                        raise EOFError("Reached EOF while reading image data")
                    run = int.from_bytes(raw_run, byteorder="big")
                    color_index = run >> 20  # upper twelve bits (32 - 20)
                    run_length = run & COLOR_MASK  # lower twenty bits
                    is_transparent = color_index == 0xFFF
                    if color_index > number_of_colors and not is_transparent:
                        raise ValueError(
                            f"Color index greater than {number_of_colors} in line {total_length//xsize + 1}"
                        )
                    line_length += run_length
                    if line_length > xsize:
                        raise ValueError(
                            f"Run too long in line: {total_length//xsize + 1}"
                        )
                    decoded_data += (
                        b"\x00\x00\x00\x00" * is_transparent
                        or palette[color_index] + b"\xFF"
                    ) * run_length
                total_length += line_length
            if buffer.read() != b"":
                raise ValueError("There are extra data at the end of the file")
            self.set_as_raw(bytes(decoded_data), rawmode="RGBA")

        if self.mode == "1":
            decode_bitonal()
        elif self.mode == "RGBA":
            decode_rgba()

        return -1, 0


class DjvuRleEncoder:
    """
    DjVu RLE encoder class.
    """

    _pushes_fd = True

    def __init__(self, mode, *args):
        self.mode = mode
        self.number_of_colors = b""
        self.palette = b""
        self.encoded_data = bytearray()

    @property
    def pushes_fd(self):
        return self._pushes_fd

    def setimage(self, im, size):
        self.im = im
        self.pixels = list(self.im)
        self.xsize, self.ysize = size[2:4]

    def setfd(self, fd):
        self.fd = fd

    def _get_row(self, row_number):
        return self.pixels[self.xsize * row_number : self.xsize * (row_number + 1)]

    def _make_bitonal_run(self, run_length):
        remaining = run_length
        while remaining > 16383:  # make max-sized runs until we get to the last run
            self.encoded_data += b"\xFF\xFF\x00"
            remaining -= 16383
        if remaining > 191:  # two-byte run
            first_byte = remaining >> 8 | 0xC0
            second_byte = remaining & 0xFF
            self.encoded_data += bytes((first_byte, second_byte))
        else:  # one-byte run
            self.encoded_data += bytes((remaining,))

    def _encode_bitonal(self):
        for row_number in range(self.ysize):
            row = self._get_row(row_number)
            pos = 0
            previous_color = 0xFF  # each line starts with a white run
            while pos < self.xsize:
                run_length = 0
                while pos < self.xsize and row[pos] == previous_color:
                    run_length += 1
                    pos += 1
                self._make_bitonal_run(run_length)
                previous_color ^= 0xFF  # toggle color

    def _make_color_run(self, color, run_length):
        if (
            isinstance(color, tuple) and len(color) == 4 and color[3] == 0x00
        ):  # check for transparency
            color_index = 0xFFF
        else:
            color_index = self.palette[color]
        remaining = run_length
        while remaining > 0xFFFFF:  # make max-sized runs until we get to the last run
            self.encoded_data += ((color_index << 20) + 0xFFFFF).to_bytes(
                4, byteorder="big"
            )
            remaining -= 0xFFFFF
        self.encoded_data += ((color_index << 20) + remaining).to_bytes(
            4, byteorder="big"
        )

    def _encode_color(self):
        for row_number in range(self.ysize):
            row = self._get_row(row_number)
            pos = 0
            previous_color = row[pos]
            while pos < self.xsize:
                run_length = 0
                while pos < self.xsize:  # measure run length
                    if row[pos] == previous_color:
                        run_length += 1
                        pos += 1
                    else:  # color changed; run ends
                        self._make_color_run(previous_color, run_length)
                        previous_color = row[pos]  # update color
                        break
                else:  # make last run of this row
                    self._make_color_run(previous_color, run_length)

    def _make_palette(self):
        if self.mode in ("L", "P"):  # inspired by Image.getcolors
            # The histogram gives an ordered list of color frequencies.
            # if h == [0, 2, 6, ...] it means there are:
            # - 0 pixels of color 0;
            # - 2 pixels of color 1;
            # - 6 pixels of color 2; (etc.)
            # For "L" (grayscale) images, color 0 is black and color 255 is white,
            # so there is a one-to-one correspondence between the index
            # in the histogram and the gray value it corresponds to.
            # For "P" (paletted) images, colors already are indices.
            h = self.im.histogram()
            colors = [color_index for (color_index, _) in enumerate(h) if _]
        else:
            fetch_colors = self.im.getcolors(4080)
            if fetch_colors:
                colors = [values for (_, values) in fetch_colors]
            else:
                raise ValueError(f"Image contains more than 4080 colors")
        self.palette = dict(zip(colors, range(len(colors))))
        self.number_of_colors = ("%d\n" % len(colors)).encode("ascii")

    def encode_to_pyfd(self):
        if self.mode == "1":
            self._encode_bitonal()
        elif self.mode == "L":
            self._make_palette()
            self._encode_color()
            self.palette = b"".join(
                bytes((color,)) * 3 for color in self.palette.keys()
            )  # convert the palette (dict) into a bytes object that can be written
        elif self.mode == "P":
            self._make_palette()
            self._encode_color()
            self.palette = self.im.getpalette()
        elif self.mode == "RGB":
            self._make_palette()
            self._encode_color()
            self.palette = b"".join(bytes(color) for color in self.palette.keys())
        elif self.mode == "RGBA":
            self._make_palette()
            self._encode_color()
            self.palette = b"".join(bytes(color)[0:3] for color in self.palette.keys())

        self.fd.write(self.number_of_colors)
        self.fd.write(self.palette)
        self.fd.write(self.encoded_data)
        return 0, 0

    def cleanup(self):  # required to exist; not sure what it is supposed to do...
        pass


def _save(im, fp, filename):
    if im.mode == "1":
        magic_number = b"R4"
    elif im.mode in ("L", "P", "RGB", "RGBA"):
        magic_number = b"R6"
    else:
        raise OSError(f"Cannot write mode {im.mode} as DJVURLE")
    fp.write(magic_number)
    fp.write(("\n%d %d\n" % im.size).encode("ascii"))
    ImageFile._save(im, fp, [("DJVURLE", (0, 0) + im.size, 0, (im.mode))])


# --------------------------------------------------------------------


Image.register_open(DjvuRleImageFile.format, DjvuRleImageFile, _accept)
Image.register_extensions(DjvuRleImageFile.format, [".rle", ".djvurle"])
Image.register_mime(DjvuRleImageFile.format, "image/x-djvurle-anymap")
Image.register_decoder(DjvuRleImageFile.format, DjvuRleDecoder)
Image.register_encoder(DjvuRleImageFile.format, DjvuRleEncoder)
Image.register_save(DjvuRleImageFile.format, _save)

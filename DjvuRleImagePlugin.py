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

from io import BytesIO
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

    def _read_magic(self, s=b""):
        while True:  # read until next whitespace
            c = self.fp.read(1)
            if c in WHITESPACE:
                break
            s = s + c
            if len(s) > 2:  # exceeded max magic number length
                break
        return s

    def _read_token(self, token=b""):
        """
        Read one token, ignoring comments.
        """

        def _ignore_comment():  # ignores rest of the line; stops at CR, LF or EOF
            while self.fp.read(1) not in b"\r\n":
                pass

        while True:  # read until non-whitespace is found
            c = self.fp.read(1)
            if c == b"#":  # found comment, ignore it
                _ignore_comment()
                continue
            if c in WHITESPACE:  # found whitespace, ignore it
                if c == b"":  # reached EOF
                    raise ValueError("Reached EOF while reading header")
                continue
            break

        token += c

        while True:  # read until next whitespace
            c = self.fp.read(1)
            if c == b"#":
                _ignore_comment()
                continue
            if c in WHITESPACE:  # token ended
                break
            token += c
            if len(token) > 9:
                raise ValueError(f"Token too long: {token}")
        return token

    def _open(self):
        """
        Load image parameters.
        """
        # read magic number
        magic_number = self._read_magic()
        try:
            self.mode = MODES[magic_number]
        except KeyError:
            raise SyntaxError("Not a DjVu RLE file") from None

        self.custom_mimetype = {
            b"R4": "image/x-djvurle-bitmap",
            b"R6": "image/x-djvurle-pixmap",
        }[magic_number]

        for ix in range(3):
            token = self._read_token()
            try:  # check token sanity
                token = int(token)
            except ValueError:
                raise ValueError(
                    f"Non-decimal-ASCII found in header: {token}"
                ) from None
            if ix == 0:  # token is the x size
                xsize = token
            elif ix == 1:  # token is the y size
                ysize = token
                if self.mode == "1":
                    number_of_colors = None  # bitonal decoder ignores this value
                    break
            elif ix == 2:  # token is the number of colors
                if not (0 < token < 4081):  # check palette size
                    raise ValueError(
                        f"Wrong number of colors: {token}; must be between 1 and 4080"
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


#
# --------------------------------------------------------------------
class DjvuRleDecoder(ImageFile.PyDecoder):
    """
    Class to decode DjVu RLE images.
    """

    def setimage(self, im, extents=None):
        super().setimage(im)

        self.xsize = self.state.xsize  # row length
        self.ysize = self.state.ysize  # number of rows
        self.size = self.xsize * self.ysize  # total number of pixels

        self.is_white_run = True
        self.line_length = 0
        self.total_length = 0
        if self.mode == "RGBA":
            self.number_of_colors = self.args[0]
            self.colors_loaded = 0
            self.palette = {}
        self.decoded_data = bytearray()  # much faster than: data = bytes()

    def _decode_bitonal(self, buffer):
        BITONAL_MASK = 0x3FFF
        bytes_read = 0

        while self.total_length < self.size:
            while self.line_length < self.xsize:
                first_byte = buffer.read(1)
                if first_byte == b"":
                    return bytes_read
                bytes_read += 1
                if first_byte > b"\xBF":  # two-byte run
                    second_byte = buffer.read(1)
                    if second_byte == b"":
                        bytes_read -= 1  # "unread" first byte
                        return bytes_read
                    bytes_read += 1
                    run_length = (
                        int.from_bytes(first_byte + second_byte, byteorder="big")
                        & BITONAL_MASK  # make the two MSBs zero
                    )
                else:
                    run_length = ord(first_byte)

                self.line_length += run_length
                if self.line_length > self.xsize:  # check line length
                    raise ValueError(
                        f"Run too long in line: {self.total_length//self.xsize + 1}"
                    )
                self.decoded_data += (
                    b"\xFF" * self.is_white_run or b"\x00"
                ) * run_length
                self.is_white_run = not self.is_white_run  # toggle run color
            # completed one line; reset counters
            self.total_length += self.line_length
            self.line_length = 0
            self.is_white_run = True  # each line starts with a white run

        return -1

    def _decode_color(self, buffer):
        COLOR_MASK = 0xFFFFF
        bytes_read = 0

        while self.colors_loaded < self.number_of_colors:  # load colors in palette
            color = buffer.read(3)
            if len(color) < 3:
                return bytes_read
            bytes_read += 3
            self.palette[self.colors_loaded] = color
            self.colors_loaded += 1

        while self.total_length < self.size:
            while self.line_length < self.xsize:
                raw_run = buffer.read(4)
                if len(raw_run) < 4:
                    return bytes_read
                bytes_read += 4
                run = int.from_bytes(raw_run, byteorder="big")
                color_index = run >> 20  # upper twelve bits (32 - 20)
                run_length = run & COLOR_MASK  # lower twenty bits
                is_transparent = color_index == 0xFFF
                if color_index > self.number_of_colors and not is_transparent:
                    raise ValueError(
                        f"Color index greater than {self.number_of_colors} in line {self.total_length//self.xsize + 1}"
                    )
                self.line_length += run_length
                if self.line_length > self.xsize:
                    raise ValueError(
                        f"Run too long in line: {self.total_length//self.xsize + 1}"
                    )
                self.decoded_data += (
                    b"\x00\x00\x00\x00" * is_transparent
                    or self.palette[color_index] + b"\xFF"
                ) * run_length
            # completed one line; reset counters
            self.total_length += self.line_length
            self.line_length = 0

        return -1

    def decode(self, buffer):
        buffer = BytesIO(buffer)

        if self.mode == "1":
            bytes_read = self._decode_bitonal(buffer)
            if bytes_read != -1:  # not finished decoding
                return bytes_read, -1
            else:
                rawmode = "1;8"
        elif self.mode == "RGBA":
            bytes_read = self._decode_color(buffer)
            if bytes_read != -1:
                return bytes_read, -1
            else:
                rawmode = "RGBA"

        if buffer.read() != b"":  # check for extra data
            raise OSError("There are extra data at the end of the file")

        self.set_as_raw(bytes(self.decoded_data), rawmode)
        return -1, 0


#
# --------------------------------------------------------------------
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
                raise ValueError("Image contains more than 4080 colors")
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


#
# --------------------------------------------------------------------
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

if __name__ == "__main__":
    from PIL import Image

    # ima = Image.open("Tests/images/hopper_1.djvurle")
    ima = Image.open("test2.djvurle")
    ima.decodermaxblock = 191
    ima.load()

    # ima = Image.open("test2.tif")
    # ima.save('test2.djvurle')

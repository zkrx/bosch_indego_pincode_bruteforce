# Bosch Indego PIN recovery

Read my blog post for a description:
https://zkre.xyz/posts/indego_pin

This script might use outdated dependencies, use a python virtual env to pull in the required libs.
This is a bit rough and you will need to get your hands dirty.

You will need to capture the necessary pictures of various screens manually beforehand. You can't
use the ones provided in this repo because your camera setup is different and the language
of your mower is likely different as well:

- sw/locked.png: after a failed pin attempt, this screen is shown.
- sw/error.png: after 3 wrong attempts, the mower locks itself and must be restarted. An error
message is shown. This is a picture of that screen.

IIRC you can use `./brute_force.py take_image` for taking a picture named test.png. `./brute_force.py take_image_and_ocr`
will take a picture and compare it with `test.png` with image hashing (no OCR perform, this is
legacy naming, sorry).

Running `./brute_force.py` will run through all pins and do the actual bruteforce.

Read the source.

This is a modified fork of https://github.com/denperss11/bosch_indego_pincode_bruteforce


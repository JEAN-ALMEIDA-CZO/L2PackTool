# Lobby Video: the client's entry screen

This is where you swap the screen that shows before picking a character. Use
one of the ready-made lobbies, or put a video of yours on it.


## Two ways

**Install lobby** puts the chosen lobby in the client as it is — map, scenery,
textures and its music. C1 through C6 are each chronicle's originals.

**Generate video and install** builds your film into the L2PackTool lobby.
That is the only one with a video screen; pick another from the list and click
here and the program uses the L2PackTool one, saying so in the log.

The lobbies travel compressed inside the program. Only the chosen one is
unpacked, and only at install time.


## The video

Formats: MP4, AVI, MKV, MOV, WEBM, GIF and animated WEBP. The video goes in
whole and centred.

The screen size is worked out to fill the game window, from a 4:3 to an
ultrawide. Filling it costs the film's edges: on a laptop screen you see about
70% of its height. Behind it sits a black panel, so no scenery shows in
whatever is left over.


## The stretch

The two sliders mark start and end; **Whole video** sends both back to the
ends.

The frame count comes from the video's frame rate, and that is what keeps the
original speed. Each frame takes about 2 MB in the package; past the limit the
rate drops on its own — the film gets choppier, but the package loads.

The preview samples the whole video and the slider picks the slice, so the
pace you see is the pace that reaches the game.

**Loop** sends the film back to the start. Without it, it plays once and
freezes on the last frame.


## The logo

An image of yours over the video. Drag it with the mouse in the preview; where
it lands is where it goes.


## Installing

The client has to be closed — the game holds the lobby files open while it
runs. Anything overwritten goes to `backup_lobby` first.

Generating the video takes a while: every frame is converted and compressed,
and the package runs past a hundred megabytes. The window may look frozen;
watch the progress bar.

After installing, the program checks whether the client has everything the
lobby's map looks for, and says what is missing.


## Why it is not an animated texture

The first version of this tab animated a texture with the `AnimNext` chain,
which is how the client animates fire and water. It passed everything you can
check from outside, and nothing happened on screen.

The film is a `MaterialSequence`: the material made to play a list over time,
on a flat mesh in front of the camera. That is what this tab builds.

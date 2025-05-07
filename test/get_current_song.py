import json

import applescript

tell_iTunes = applescript.AppleScript(
    """
on is_running(appName)
	tell application "System Events" to (name of processes) contains appName
end is_running
on Playing()
	on is_running(appName)
	tell application "System Events" to (name of processes) contains appName
end is_running

set MusicRunning to is_running("Music")

if MusicRunning then
	tell application "Music"
		set songTitle to the name of the current track
		set songArtist to the artist of the current track
		set songAlbum to the album of the current track
		
		set result to songArtist & "%-%" & songTitle
		
		if player state is playing then
			return result
		else
			return "None"
		end if
	end tell
end if
end Playing
"""
)

output = tell_iTunes.call("Playing").split("%-%")

print(
    json.dumps({"Artist": output[0], "song": output[1], "album": output[2]}, indent=4)
)

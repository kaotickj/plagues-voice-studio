"""Maintainer utility to regenerate editable, quality-controlled dialogue.json."""
import json
from pathlib import Path
scenes=[]
def scene(id,category,mood,setup,thought,landing,sponsor=None):
    data=dict(id=id,category=category,mood=mood,setup=setup,thought=thought,landing=landing)
    if sponsor: data['sponsor']=sponsor
    scenes.append(data)

scene('open-lights','Broadcast opener','Comforting',
      ["There's still a lamp burning in somebody's window tonight.", "Goodneighbor's holding on to its last few lights tonight.", "Out there, one little window's still lit against the dark."],
      ["Could be a welcome home. Could be somebody refusing to give up.", "You never know who's waiting on the other side of a dark street."],
      ["Wherever this finds you, {dj} is here with another hour of {station}.", "I'm {dj}. Come keep me company on {station}."])
scene('open-rain','Broadcast opener','Atmospheric',
      ["The rain's working its way down Goodneighbor's old brick tonight.", "Wet pavement's making the neon look twice as tired."],
      ["The streets don't get any cleaner, but they do get a little quieter.", "Seems like every drop knows a sad tune already."],
      ["I'm {dj}, and this is {station}. Pull up a chair.", "Stay inside a while. {dj} here, keeping {station} on the air."])
scene('open-road','Broadcast opener','Reflective',
      ["If you made it back off the road today, count that as a victory.", "Another hard day's found its way into the rearview mirror."],
      ["Out here even the short trips can feel like a lifetime.", "Sometimes getting home is all the good news you need."],
      ["I'm {dj}. Welcome back to {station}.", "This is {station}, and I'm {dj}. Glad you made it."])
scene('open-coffee','Broadcast opener','Wry',
      ["The coffee's burnt, the chair's uneven, and the transmitter's holding by a prayer.", "My coffee's lost the will to live, but the radio's still got some fight."],
      ["That's what passes for a fine evening around these parts.", "I'd complain, but complaints cost more than coffee now."],
      ["I'm {dj}, and you're listening to {station}.", "Pull up a chair. {dj} is on the air at {station}."])
scene('open-lonely','Broadcast opener','Melancholy',
      ["The city's full of people who still feel alone tonight.", "Every empty stool tells a story after midnight."],
      ["Nobody can make every silence disappear.", "There's no shame in wanting somebody to hear you."],
      ["I'm {dj}. For a little while, let {station} keep you company.", "You've got {station}. I'm {dj}, and I'm not going anywhere just yet."])
scene('id-basic','Station ID','Comforting',
      ["Still here, neighbor.", "You're in good company tonight."],
      ["No fancy promises. Just songs with some miles on them.", "That's about all we need."],
      ["I'm {dj}. This is {station}.", "You're listening to {station} with {dj}."])
scene('id-weather','Station ID','Atmospheric',
      ["From the crooked streets of Goodneighbor, we're still broadcasting.", "Under the hum of old neon, our signal's still reaching out."],
      ["As long as these old wires hold, we'll be around.", "Some nights that little signal is enough."],
      ["This is {station}. I'm {dj}.", "{station}, with {dj} keeping watch."])
scene('id-humor','Station ID','Wry',
      ["No guarantees about the reception. None about the coffee either.", "Broadcasting on borrowed time and a suspicious amount of duct tape."],
      ["But if you can hear me, the evening's not a total loss.", "Somehow, the needle still drops where it's meant to."],
      ["{station}. I'm {dj}.", "You're tuned to {station} with {dj}."])
scene('break-second-chance','Station break','Reflective',
      ["Goodneighbor's never been the place you come to look respectable.", "Around here, folks learn not to ask too much about yesterday."],
      ["Most everybody's trying to get one thing right before the day is over.", "There's room for a second chance if you make a little space for it."],
      ["No judgments from this microphone. I'm {dj}, and this is {station}.", "Whatever yesterday cost you, you're here tonight. {station}, with {dj}."])
scene('break-quiet','Station break','Comforting',
      ["Maybe the day asked more from you than you had to give.", "If today wore you down, I hope you're somewhere safe now."],
      ["Don't mistake being tired for being finished.", "You can set the weight down for a song or two."],
      ["Stay a while. I'm {dj}, and this is {station}.", "Take what rest you can find. {station}, with {dj}."])
scene('break-noise','Station break','Wry',
      ["Somebody's arguing with a busted generator down the street.", "I heard somebody threaten a vending machine with a tire iron earlier."],
      ["The generator appears to be winning.", "Can't say the machine looked worried."],
      ["Goodneighbor hasn't changed a bit. I'm {dj} on {station}.", "That's a normal Tuesday around here. {station}, with {dj}."])
scene('break-absence','Station break','Melancholy',
      ["There's an empty chair at more than one table tonight.", "Every neighborhood has names nobody says aloud anymore."],
      ["Sometimes remembering is the best we can do.", "A song won't bring somebody back, but it can keep a little of them close."],
      ["This next stretch is for the ones we're missing. {station}, with {dj}.", "Keep their memory warm tonight. I'm {dj}, here on {station}."])
scene('break-night','Station break','Atmospheric',
      ["The old signs are buzzing above the street again.", "Somewhere beyond the walls, the Commonwealth's gone almost quiet."],
      ["Quiet doesn't mean peaceful, but it gives a song room to breathe.", "Some nights the hum of a radio is the friendliest sound you'll hear."],
      ["Leave your dial right here. {station}, with {dj}.", "We're still on the air. I'm {dj}, and this is {station}."])
scene('intro-memory','Song introduction','Melancholy',
      ["Some records find the hurt you thought you'd put away.", "There's a kind of song that knows exactly what you miss."],
      ["It's not always easy listening. That doesn't make it any less worth hearing.", "The right voice can make an old memory feel brand-new."],
      ["Here's {title}{artist_phrase}. Let it say what it needs to.", "Up next is {title}{artist_phrase}. Listen close."])
scene('intro-swing','Song introduction','Wry',
      ["If your boots still work, they might have a job to do.", "This one's liable to wake up a room full of tired feet."],
      ["Don't blame me if the floor starts complaining.", "I take no responsibility for broken furniture."],
      ["Coming up, {title}{artist_phrase}. Turn it up.", "Let's hear {title}{artist_phrase}. Give it some room."])
scene('intro-relief','Song introduction','Comforting',
      ["You don't have to solve a single problem for the next few minutes.", "Whatever's chasing you can wait until this record ends."],
      ["A little music won't repair the world. It might make it easier to face.", "For now, the only job is to listen."],
      ["Here's {title}{artist_phrase}. This one's for you.", "Up next, {title}{artist_phrase}. Take a load off."])
scene('intro-soul','Song introduction','Reflective',
      ["A good blues song tells the truth without making a speech.", "Some singers can put a whole hard life into one line."],
      ["It's a rare gift, saying what everybody else is too tired to say.", "When that happens, the best thing a DJ can do is get out of the way."],
      ["Here's {title}{artist_phrase}. I'll let the music speak.", "Coming up, {title}{artist_phrase}. No introduction can improve on it."])
scene('intro-rain','Song introduction','Atmospheric',
      ["That wind outside's tapping against the window again.", "The rain's settled in for a long evening."],
      ["Good weather for staying in close to the speaker.", "Seems like the right kind of night for a record with some miles on it."],
      ["Next on the turntable, {title}{artist_phrase}.", "Let's play {title}{artist_phrase}. Stay dry out there."])
scene('outro-echo','Song outro','Melancholy',
      ["That last note's still hanging in the room.", "I almost hate to let the silence back in after that one."],
      ["Some songs leave you thinking about somebody who isn't here.", "That kind of ache can take its time leaving."],
      ["That was {title}{artist_phrase}. You're with {station}.", "You just heard {title}{artist_phrase}. I'm {dj}, still here on {station}."])
scene('outro-grit','Song outro','Wry',
      ["That record came through with both elbows out.", "If that one didn't shake the dust loose, nothing will."],
      ["I'll have to check whether the old speaker's still attached to the wall.", "We might owe the furniture an apology."],
      ["That was {title}{artist_phrase}. This is {station}.", "You heard {title}{artist_phrase}. I'm {dj}, and we've got more coming."])
scene('outro-reflect','Song outro','Reflective',
      ["That's the kind of performance that stays with you.", "There's a lot of living tucked inside a tune like that."],
      ["Sometimes the rough edges tell more truth than the polished ones.", "There's no need to tidy up what a good singer laid bare."],
      ["You just heard {title}{artist_phrase}. I'm {dj} on {station}.", "That was {title}{artist_phrase}. Keep your dial here at {station}."])
scene('outro-warm','Song outro','Comforting',
      ["Hope that song gave you a moment to breathe.", "I hope that one found you at the right time."],
      ["One decent melody can make a hard night less lonely.", "Sometimes a few good notes really are enough."],
      ["That was {title}{artist_phrase}. More good company ahead on {station}.", "You just heard {title}{artist_phrase}. I'm {dj}, keeping {station} going."])
scene('outro-street','Song outro','Atmospheric',
      ["The street outside's gone quiet, but that last note didn't.", "Even the neon seems to have stopped buzzing for a second."],
      ["That's the sort of song you carry out the door with you.", "Some performances make the whole city feel a little smaller."],
      ["That was {title}{artist_phrase}. You're tuned to {station}.", "You just heard {title}{artist_phrase}. More from {station} in a moment."])
scene('close-home','Broadcast closer','Comforting',
      ["The records are back in their sleeves, and the night's getting old.", "That's our last spin for the evening."],
      ["If you're headed home, I hope someone's left a light on.", "Thanks for sharing a little piece of your night with me."],
      ["I'm {dj}. Goodnight from {station}. Look after each other.", "This is {dj} signing off from {station}. Make it home safe."])
scene('close-dark','Broadcast closer','Melancholy',
      ["Another evening's slipped away before we could hold onto it.", "Even the last record eventually reaches the run-out groove."],
      ["There are things we couldn't put right tonight. Tomorrow we'll try again.", "Maybe the morning will be a little kinder."],
      ["I'm {dj}. This has been {station}. Goodnight, neighbor.", "From {station}, this is {dj} wishing you some peace tonight."])
scene('close-wry','Broadcast closer','Wry',
      ["The transmitter's warm and my coffee's officially beyond saving.", "The old turntable's earned itself a rest."],
      ["I reckon we've pushed our luck far enough for one night.", "The equipment and I have agreed to stop arguing until tomorrow."],
      ["I'm {dj}, signing off from {station}. Don't do anything I wouldn't do.", "That's all from {station}. I'm {dj}. Keep your boots dry."])
scene('close-street','Broadcast closer','Atmospheric',
      ["The neon's thinning out and the alleys have gone still.", "There's a faint light over Goodneighbor, but the night belongs to the street now."],
      ["Somebody will be up to greet the dawn. Maybe it'll be you.", "We'll leave the quiet to the late walkers."],
      ["I'm {dj}, and this has been {station}. Goodnight.", "Until next time, {dj} signing off from {station}."])
scene('close-account','Broadcast closer','Reflective',
      ["We played what we could, and said what needed saying.", "Every show ends before all the stories are finished."],
      ["Leave a little room for tomorrow's stories.", "Nobody knows what the next day brings, but there's always another song."],
      ["I'm {dj}. Thanks for listening to {station}. Take care.", "From {station}, this is {dj}. We'll meet on the dial again."])
scene('ad-third-rail','Ad / promo','Wry',
      ["Need a place where the stools are steady and the conversation isn't?", "If you've spent all day bargaining with trouble, you might need a chair."],
      ["The Third Rail has its own ideas about a peaceful evening.", "The Third Rail isn't promising to fix your problems, but it'll pour you something while you think."],
      ["Drop by the Third Rail in Goodneighbor. Tell them you heard about it on {station}.", "The Third Rail, right here in Goodneighbor. A fictional spot from your friends at {station}."],sponsor='The Third Rail')
scene('ad-den','Ad / promo','Reflective',
      ["Got a memory you keep coming back to?", "If yesterday's been knocking louder than today, there's a place you might know."],
      ["Some memories deserve care, and some deserve questions.", "There's a difference between remembering and moving back in."],
      ["The Memory Den in Goodneighbor. Take your memories seriously.", "Ask around about the Memory Den. Remember to keep a foot in the present."],sponsor='Memory Den')
scene('ad-station','Ad / promo','Comforting',
      ["Couldn't sleep? Neither could we.", "When the streets are quiet, your radio doesn't have to be."],
      ["We're just keeping a light on for anybody who needs one.", "A little music travels farther than you think."],
      ["{station}. Honest songs, no shiny promises.", "Tune in to {station}. We're glad you're here."],sponsor='Goodneighbor Blues')
scene('ad-station-wry','Ad / promo','Wry',
      ["Our records are scratched, and so are most of our listeners.", "Fancy broadcasting equipment? No. Excellent taste? That's debatable."],
      ["At least we're not charging admission to your own radio.", "All we can promise is another song."],
      ["{station}. Keep the dial right where it is.", "That's {station}. Accept no imitations."],sponsor='Goodneighbor Blues')
# Generic advertiser needs to stay strictly neutral and avoid invented properties or services.
scene('ad-custom','Ad / promo','Reflective',
      ["A message tonight from {sponsor}.", "Taking a moment for our friends at {sponsor}."],
      ["Before spending your caps, be sure to ask what they offer and what it costs.", "We won't pretend to know what they can do for you. Ask them directly."],
      ["Find out more about {sponsor} before making a deal. Now, back to {station}.", "That's {sponsor}. You're listening to {station}."])

path = Path(__file__).with_name('dialogue_base_33.json')
# Legacy base collection only: never overwrite the expanded production database.
path.write_text(json.dumps({'version':1,'scenes':scenes},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('Created',path,'with',len(scenes),'curated scene families')

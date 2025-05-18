# EliteDangerous

## Architect Tracker
Displays commodities required, provided and needed when you land at a construction site and tracks cargo in your fleet carrier and starship.
The focus is to create a simple to use and hands free tracker for system colonisation. I will be adding features often so check back here often. This was created using ChatGPT. It probably took me as long to create as a human could have programmed manually but I have no experience programming in Python or for the EDMC so it is kind of impressive.

![Screenshot](https://github.com/kol19pl/EliteDangerous-ArchictectTracker/blob/main/Zrzut%20ekranu%202025-05-01%20131935.png?raw=true)

Discussion
https://forums.frontier.co.uk/threads/colonization-tool-architect-tracker.636854/#post-10621804



### Install Instructions from relese
1. Go the the ED: Marketplace Connector plugins folder.
2. Extract "Architect Tracker.zip" into a plugins folder.
3. Start EDMC.


### Install Instructions from sorce
1. Create a directory called "Architect Tracker" in the the ED: Marketplace Connector plugins folder.
2. Save the code all file from "Architect Tracker".
3. Start EDMC.

### Usage
+ When you land at a construction site the plugin will (after a few moments) list all the commodities and amounts required, provided and needed. You can switch between sites from the dropdown list in the upper left.
+ The "For Sale" column display a check mark if the commodity is for sale at the last commodity market you accessed.
+ To display\update your fleet carrier cargo, open the "Carrier Management" in-game tool. The quantities will appear after a few moments (this can take a while and occasionaly display incorrect number). If you are also selling commodities from your fleet carrier, you will need to update this list as needed (sales are not tracked).
+ Starship cargo will be displayed automaticly.
+ The shortfall column displays how much of a commodity you still need to aquire.


### Notable Changes
+ 2025/05/18 : Ad bag raport function
+ 2025/05/18 : Ad update function
+ 2025/05/18 : bag fix
+ 2025/05/18 : The code has been split for easier editing. Improved structure removal functions.
+ 2025/05/12 : Addet independent theme blac and white
+ 2025/05/11 : Aded System sorting station, Delite stations in setings , Est trip for construction and completion %
+ 2025/05/03 : Adaptation for new naming conwention for colonisation ship
+ 2025/05/01 : Deleted unworking style , ad setings for beter use
+ 2025/04/12 : Added support for multiple construction sites. Sites are removed automaticly when they are completed.
+ 2025/04/19 : Added feature - commodities required for construction are highlighted when a commodity market is opened.
+ 2025/04/25 : Added fleet carrier cargo information - open the carrier management tool in-game to populate\refresh this list. NOTE: Tracks cargo transfers to/from FC but not market sales.
+ 2025/04/30 : Added starship cargo tracking and dark theme colours.

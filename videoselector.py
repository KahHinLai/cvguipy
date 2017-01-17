#!/usr/bin/python
"""A script for running a cvTrajOverlay player with a video, and optionally adding overlay from database of trajectory data.."""

import os, sys, time, argparse, traceback
import rlcompleter, readline
import numpy as np
import threading
import multiprocessing
import cvgui

# Entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program for selecting points and regions in a video frame for use in computer vision applications.")
    parser.add_argument('videoFilename', help="Name of the video file to play.")
    parser.add_argument('-f', dest='configFilename', help="Name of file containing point/region locations.")
    parser.add_argument('-s', dest='configSection', help="Section of the config file containing point/region locations. Defaults to name of the video file (without the path) if not specified.")
    parser.add_argument('-pk', dest='printKeys', action='store_true', help="Print keys that are read from the video window (useful for adding shortcuts and other functionality).")
    parser.add_argument('-pm', dest='printMouseEvents', type=int, nargs='*', help="Print mouse events that are read from the video window (useful for adding other functionality). Optionally can provide a number, which signifies the minimum event flag that will be printed.")
    parser.add_argument('-r', dest='clickRadius', type=int, default=10, help="Radius of clicks on the image (in pixels).")
    parser.add_argument('-i', dest='interactive', action='store_true', help="Play the video in a separate thread and start an interactive shell.")
    args = parser.parse_args()
    videoFilename = args.videoFilename
    configFilename = args.configFilename
    configSection = args.configSection
    
    # create the GUI object
    player = cvgui.cvPlayer(videoFilename, configFilename=configFilename, configSection=configSection, printKeys=args.printKeys, printMouseEvents=args.printMouseEvents, clickRadius=args.clickRadius)
    
    # show the window
    if args.interactive:
        player.runInThread()
        time.sleep(2)
        
        # once the video is playing, make this session interactive
        os.environ['PYTHONINSPECT'] = 'Y'           # start interactive/inspect mode (like using the -i option)
        readline.parse_and_bind('tab:complete')     # turn on tab-autocomplete
    else:
        player.run()
    
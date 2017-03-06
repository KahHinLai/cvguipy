#!/usr/bin/python
"""Classes for working with homographies easily."""

import os, sys, time, argparse, traceback
import ast
import numpy as np
import multiprocessing, Queue
import cvgui, cvgeom
import cv2

class Homography(object):
    """A class containing a homography computed from a set of point
       correspondences taken from an aerial image and a video frame."""
    # TODO split this up into static/class method(s) to clean it up
    def __init__(self, aerialPoints=None, cameraPoints=None, unitsPerPixel=1.0, homographyFilename=None, worldPoints=None, homography=None, videoWidth=None, videoHeight=None):
        self.aerialPoints = cvgeom.ObjectCollection(aerialPoints) if aerialPoints is not None else aerialPoints
        self.cameraPoints = cvgeom.ObjectCollection(cameraPoints) if cameraPoints is not None else cameraPoints
        self.worldPoints = cvgeom.ObjectCollection(worldPoints) if worldPoints is not None else worldPoints
        self.unitsPerPixel = unitsPerPixel
        self.homographyFilename = None if homographyFilename is not None and not os.path.exists(homographyFilename) else homographyFilename
        self.videoWidth = videoWidth
        self.videoHeight = videoHeight
        
        self.worldPts = None
        self.cameraPts = None
        self.homography = np.loadtxt(self.homographyFilename) if self.homographyFilename is not None else homography
        self.inverted = None
        self.mask = None
        self.worldPointDists = None
        self.worldPointSquareDists = None
        self.worldPointError = None
        
        if self.homography is not None:
            self.invert()
        
    @staticmethod
    def fromString(s, **kwargs):
        """Load a homography from a string (like [[a,b,c],[d,e,f],[g,h,i]]),
           for instance from a configuration file."""
        return Homography(homography=ast.literal_eval(s), **kwargs)
    
    @staticmethod
    def fromArray(homArray, **kwargs):
        """
        Construct the homography object from a numpy array.
        """
        return Homography(homography=homArray, **kwargs)
    
    @staticmethod
    def getObjColFromArray(pArray):
        """Get an ObjectCollection of points from a 2xN array."""
        d = cvgeom.ObjectCollection()
        i = 1
        for x, y in zip(*pArray):
            d[i] = cvgeom.imagepoint(x, y, index=i)
            i += 1
        return d

    @staticmethod
    def getPointArray(points):
        """Get an Nx2 floating-point numpy array from an ObjectCollection of points,
           or a single point."""
        if isinstance(points, cvgeom.ObjectCollection):
            a = []
            for i in sorted(points.keys()):
                a.append(points[i].asTuple())
        elif isinstance(points, cvgeom.imagepoint):     # wrap in a list if only one point
            a = [points.asTuple()]
        return np.array(a, dtype=np.float64)
    
    @staticmethod
    def invertHomography(homography):
        invH = np.linalg.inv(homography)
        invH /= invH[2,2]
        return invH
    
    def getWorldGrid(self):
        """
        Get an array of points that represent all possible world space coordinates that
        can be represented in the camera frame give its resolution.
        """
        if all([self.videoWidth, self.videoHeight, self.homography is not None]):
            # make a meshgrid of all possible coordinates in the camera frame
            mg = np.mgrid[0:self.videoHeight,0:self.videoWidth]
            
            # project the pixel coordinates to world space
            return self.projectPointArray(mg.reshape(2,-1)).reshape(2,self.videoHeight,self.videoWidth)
    
    def getMaxValue(self):
        """
        Determine the maximum position value in world units that can be measured in
        the camera frame.
        """
        wgp = self.getWorldGrid()
        if wgp is not None:
            return np.max(wgp)
    
    def computePrecision(self):
        """
        Compute the precision allowed by the camera frame in world units. Returns the
        value of the smallest change that can be represented in the image, calculated
        as the smallest distance in world space between any two neighboring pixels in
        the camera frame.
        """
        wgp = self.getWorldGrid()
        if wgp is not None:
            
            # calculate distance to the 3 next points (i,j+1), (i+1, j), and (i+1,j+1)
            # distance to point down
            wgup = wgp[:,0:-1,:]
            wgdown = wgp[:,1:,:]
            wgudsq = (wgup-wgdown)**2
            udDistMin = np.min(np.sqrt(wgudsq[0]+wgudsq[1]))
            
            # distance to point to right
            wgleft = wgp[:,:,0:-1]
            wgright = wgp[:,:,1:]
            wglrsq = (wgleft-wgright)**2
            lrDistMin = np.min(np.sqrt(wglrsq[0]+wglrsq[1]))
            
            # distance to diagonal point
            wgo = wgp[:,0:-1,0:-1]
            wgdiag = wgp[:,1:,1:]
            wgdiagsq = (wgo-wgdiag)**2
            diagDistMin = np.min(np.sqrt(wgdiagsq[0]+wgdiagsq[1]))
            
            return min(udDistMin, lrDistMin, diagDistMin)
    
    def toString(self):
        if self.homography is not None:
            return str([list(h) for h in self.homography])
    
    def savetxt(self, filename):
        if self.homography is not None:
            np.savetxt(filename, self.homography)
    
    def projectPointArray(self, points, invert=False):
        if len(points) > 0:
            augmentedPoints = np.append(points,[[1]*points.shape[1]], 0)
            hom = self.inverted if invert else self.homography
            prod = np.dot(hom, augmentedPoints)
            return prod[0:2]/prod[2]
        else:
            return np.array([], dtype=np.float64)
    
    def findHomography(self):
        """Compute the homography from the two sets of points and the given units."""
        if self.aerialPoints is not None:
            self.worldPts = self.unitsPerPixel*Homography.getPointArray(self.aerialPoints)
        elif self.worldPoints is not None:
            self.worldPts = Homography.getPointArray(self.worldPoints)
        self.cameraPts = Homography.getPointArray(self.cameraPoints)
        self.homography, self.mask = cv2.findHomography(self.cameraPts, self.worldPts)
        self.invert()
        
    def invert(self):
        if self.homography is not None:
            self.inverted = Homography.invertHomography(self.homography)
    
    def projectToAerial(self, points, objCol=True):
        """Project points from image space to the aerial image (without units) for plotting."""
        if self.homography is not None:
            pts = self.projectPointArray(Homography.getPointArray(points).T)/self.unitsPerPixel
            pts = Homography.getObjColFromArray(pts) if objCol else pts
            return pts
    
    def projectToWorld(self, points, objCol=True):
        """Project an ObjectCollection of points in video space to world
           space (in units of unitsPerPixel) using the homography."""
        if self.homography is not None:
            pts = self.projectPointArray(Homography.getPointArray(points).T)
            pts = Homography.getObjColFromArray(pts) if objCol else pts
            return pts
            
    def projectToImage(self, points, fromAerial=True, objCol=True):
        """Project an ObjectCollection of points from aerial or world space to image space."""
        if self.homography is not None:
            pArray = Homography.getPointArray(points).T
            ipts = pArray*self.unitsPerPixel if fromAerial else pArray
            pts = self.projectPointArray(ipts, invert=True)
            pts = Homography.getObjColFromArray(pts) if objCol else pts
            return pts
    
    def calculateError(self, squared=True):
        """Calculate the error (average of distances (squared, by default) between corresponding points) of
           the homography in world units."""
        # take the aerial points and calculate their position in world coordinates (i.e. multiply by unitsPerPixel)
        worldPts = Homography.getPointArray(self.aerialPoints)*self.unitsPerPixel
        
        # project the camera points to world coordinates with projectToWorld
        projWorldPts = self.projectToWorld(self.cameraPoints, objCol=False)
        
        # calculate the error ([squared] distance) between each pair of points
        self.worldPointDists = np.sqrt(np.sum((worldPts-projWorldPts)**2, axis=1))       # calculate the distance between corresponding points
        self.worldPointSquareDists = self.worldPointDists**2
        
        # average the error values (not summed, so we don't penalize picking more points)
        err = np.sum(self.worldPointSquareDists) if squared else np.sum(self.worldPointDists)
        self.worldPointError = err/len(self.aerialPoints)
        return self.worldPointError
    
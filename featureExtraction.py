import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt
from itertools import compress

class featureExtraction:
    def __init__(self,image_list,k=2,method="BF",match_threshold=100,maximum_matches=6,feature_correspondences=4,RANSAC_iterations=500):
        self.image_list = image_list
        self.num_images = len(image_list)
        self.keypoints = []
        self.descriptors = []
        self.matches = np.empty((self.num_images,self.num_images),dtype=object)
        self.inliers = np.zeros((self.num_images,self.num_images),dtype=int)
        self.homographies = self.initialize_homographies()
        self.adjacency_matrix = np.zeros((self.num_images,self.num_images),dtype=int)
        self.k = k
        self.method = method
        self.ratio = 0.7
        self.match_threshold = match_threshold
        self.maximum_matches = maximum_matches
        self.feature_correspondences = feature_correspondences
        self.RANSAC_iterations = RANSAC_iterations

    def initialize_homographies(self):
        # Initialize homographies to identity matrix
        # Input:
        #   self.num_images: number of images
        # Output:
        #   self.homographies: list of homographies
        homographies = np.empty((self.num_images,self.num_images),dtype=object)
        for i in range(self.num_images):
            for j in range(self.num_images):
                homographies[i,j] = np.eye(3)

        return homographies
    
    def process_maximum_matches(self):
        # Only consider the top maximum_matches matches for and image i
        # Input:
        #   self.matches: list of matches for each image pair
        #   self.maximum_matches: maximum number of matches to consider
        # Output:
        #   self.matches: list of matches for each image pair

        # Loop through all image pairs
        for i in range(self.num_images):
            match_count = np.zeros(self.num_images)
            for j in range(self.num_images):
                if i == j:
                    continue
                match_count[j] = len(self.matches[i,j])
            # Sort matches by number of matches
            sorted_matches = np.argsort(match_count)[::-1]
            # Select top maximum_matches matches
            if len(sorted_matches) > self.maximum_matches:
                sorted_matches = sorted_matches[:self.maximum_matches]

            # Loop through all images
            for j in range(self.num_images):
                if i == j:
                    continue
                if j not in sorted_matches:
                    self.matches[i,j] = None

    def get_H_matrix(self,image_index_1,image_index_2):
        # Get homography matrix for image pair
        # Input:
        #   image_index_1: index of image 1
        #   image_index_2: index of image 2
        # Output:
        #   H: homography matrix

        matches = self.matches[image_index_1,image_index_2]
        keypoints_1 = self.keypoints[image_index_1]
        keypoints_2 = self.keypoints[image_index_2]

        src_pts = np.empty((len(matches),2),dtype=float)
        dst_pts = np.empty((len(matches),2),dtype=float)

        # Create correspondence matrix
        correspondences = np.zeros((len(matches),self.feature_correspondences),dtype=float)
        for i in range(len(matches)):
            m = matches[i]
            correspondences[i,0] = src_pts[i,0] = keypoints_1[m.queryIdx].pt[0]
            correspondences[i,1] = src_pts[i,1] = keypoints_1[m.queryIdx].pt[1]
            correspondences[i,2] = dst_pts[i,0] = keypoints_2[m.trainIdx].pt[0]
            correspondences[i,3] = dst_pts[i,1] = keypoints_2[m.trainIdx].pt[1]

        src_pts, dst_pts = np.float32(src_pts), np.float32(dst_pts)

        # Compute homography matrix
        H, mask = cv.findHomography(src_pts, dst_pts, cv.RANSAC, ransacReprojThreshold=1.0)

        return H, mask, correspondences


    def validate_homography(self,image_index_1,image_index_2,H,correspondences,mask):
        # Get inliers for image pair
        # Input:
        #   image_index_1: index of image 1
        #   image_index_2: index of image 2
        # Output:
        #   inliers: list of inliers
        img_1 = self.image_list[image_index_1]
        img_2 = self.image_list[image_index_2]

        if H is None:
            return False
        else:
            alpha = 0.8
            beta = 0.3

            mask_1 = np.ones_like(img_1, dtype=np.uint8)
            mask_2 = np.ones_like(img_1, dtype=np.uint8)
            mask_2 = cv.warpPerspective(np.ones_like(img_2, dtype=np.uint8), dst=mask_2, M=H, dsize=mask_1.shape[::-1])
            overlap = mask_1 * mask_2

            area = np.sum(mask)
            matchpoints_1 = correspondences[:, :2]
            overlapping_matches = matchpoints_1[overlap[matchpoints_1[:, 1].astype(np.int64), matchpoints_1[:, 0].astype(np.int64)] == 1]

            return area > (alpha + (beta * overlapping_matches.shape[0]))


    def compute_homograpies(self):
        # Compute homographies for all images
        # Input:
        #   self.image_list: list of images
        #   self.keypoints: list of keypoints for each image
        #   self.matches: list of matches for each image pair
        # Output:
        #   self.homographies: list of homographies

        # Loop through all image pairs
        for i in range(self.num_images):
            for j in range(self.num_images):
                # Skip if image pair already computed
                if i == j:
                    continue
                if self.homographies[i,j] is not None:
                    continue
                # Compute homography
                H , mask, correspondences = self.get_H_matrix(i,j)
                # Validate homography
                isValid = self.validate_homography(i,j,H,correspondences,mask)

                if isValid:
                    self.homographies[i,j] = H
                    self.homographies[j,i] = np.linalg.inv(H)
                    self.inliers[i,j] = np.sum(mask)
                    self.inliers[j,i] = np.sum(mask)
                    self.matches[i,j] = list(compress(self.matches[i,j],mask))
                else:
                    self.homographies[i,j] = None
                    self.homographies[j,i] = None
                    self.inliers[i,j] = 0
                    self.inliers[j,i] = 0
                    self.matches[i,j] = None



    def extractSIFTFeatures(self,img):
        # Extract SIFT features from an image
        # Input:
        #   img: image
        # Output:
        #   features: SIFT features
        #   descriptors: SIFT descriptors

        # Create SIFT object
        sift = cv.SIFT_create()
        # Find keypoints and descriptors
        keypoints, descriptors = sift.detectAndCompute(img,None)
        return keypoints, descriptors
    
    def computeFeatures(self):
        # Compute features for all images
        # Input:
        #   self.image_list: list of images
        # Output:
        #   self.keypoints: list of keypoints for each image
        #   self.descriptors: list of descriptors for each image

        # Loop through all images
        for image in self.image_list:
            # Extract SIFT features
            keypoints, descriptors = self.extractSIFTFeatures(image)
            # Add keypoints and descriptors to lists
            self.keypoints.append(keypoints)
            self.descriptors.append(descriptors)

    def matchFeatures(self,descriptors_1,descriptors_2):
        # Match SIFT features from two images
        # Input:
        #   descriptors_1: SIFT descriptors from image 1
        #   descriptors_2: SIFT descriptors from image 2
        #   method: matching method, "BF" for brute force, "FLANN" for FLANN
        #   k: number of nearest neighbors in KNN
        # Output:
        #   matches: SIFT matches

        if self.method == "BF":
            # Create BFMatcher object
            bf = cv.BFMatcher()
            # Match descriptors
            matches = bf.knnMatch(descriptors_1,descriptors_2, k=self.k)
        elif self.method == "FLANN":
            FLANN_INDEX_KDTREE = 1
            index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
            search_params = dict(checks = 50)
            flann = cv.FlannBasedMatcher(index_params, search_params)
            matches = flann.knnMatch(descriptors_1,descriptors_2,k=self.k)

        good_matches = []
        for m,n in matches:
            if m.distance < self.ratio*n.distance:
                good_matches.append(m)

        if len(good_matches) > self.match_threshold:
            return good_matches
        else:
            return []
    
    def computeMatches(self):
        # Compute matches for all images
        # Input:
        #   self.image_list: list of images
        #   self.descriptors: list of descriptors for each image
        # Output:
        #   matches: list of matches for each image pair

        # Loop through all image pairs
        for i in range(self.num_images):
            for j in range(self.num_images):
                # Skip if image pair already computed
                if i == j:
                    continue
                # Compute matches
                matches = self.matchFeatures(self.descriptors[i],self.descriptors[j])
                # Add matches to list
                self.matches[i,j] = matches
                

    def plot_matches(self, image_index_1, image_index_2):
        # Plot SIFT matches
        # Input:
        #   img_1: image 1
        #   img_2: image 2
        #   keypoints_1: SIFT keypoints from image 1
        #   keypoints_2: SIFT keypoints from image 2
        #   matches: SIFT matches
        #   title: title of the plot

        img_1 = self.image_list[image_index_1]
        img_2 = self.image_list[image_index_2]
        keypoints_1 = self.keypoints[image_index_1]
        keypoints_2 = self.keypoints[image_index_2]
        matches = self.matches[image_index_1,image_index_2]
        title = "SIFT matches between image " + str(image_index_1) + " and image " + str(image_index_2)

        img_1 = cv.cvtColor(img_1, cv.COLOR_BGR2RGB)
        img_2 = cv.cvtColor(img_2, cv.COLOR_BGR2RGB)

        # Create a new plot
        plt.figure(figsize=(15, 15))
        plt.axis('off')
        # Set plot title
        plt.title(title)
        # Plot image 1
        plt.imshow(img_1)
        # Get image 1 dimensions
        h_1, w_1 = img_1.shape[:2]
        # Plot image 2
        plt.imshow(img_2, extent=(w_1, w_1 + img_2.shape[1], img_2.shape[0], 0))
        # Plot lines between matches
        for match in matches:
            # Get the matching keypoints for each of the images
            img1_idx = match.queryIdx
            img2_idx = match.trainIdx
            # x - columns
            # y - rows
            (x1,y1) = keypoints_1[img1_idx].pt
            (x2,y2) = keypoints_2[img2_idx].pt
            plt.plot([x1, x2+w_1], [y1, y2], 'c', linewidth=1)
            plt.plot(x1, y1, 'ro')
            plt.plot(x2+w_1, y2, 'go')
        # Show the plot
        plt.show()
    
    def computeAdjacencyMatrix(self):
        # Compute adjacency matrix from matches
        # Input:
        #   matches: list of matches for each image pair
        # Output:
        #   adjMatrix: adjacency matrix

        # Loop through all image pairs
        for i in range(self.num_images):
            for j in range(self.num_images):
                # Skip if image pair already computed
                if i == j:
                    continue
                # Compute matches
                matches = self.matches[i,j]
                if matches is None:
                    continue
                # Add matches to list
                self.adjacency_matrix[i,j] = 1 if len(matches) > 0 else 0
    
    def run(self):
        print("Extracting SIFT features...")
        self.computeFeatures()
        print("Generating matches...")
        self.computeMatches()
        print("Processing matches...")
        self.process_maximum_matches()
        print("Computing homographies...")
        self.compute_homograpies()
        print("Computing adjacency matrix...")
        self.computeAdjacencyMatrix()


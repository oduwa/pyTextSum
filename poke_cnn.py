# -*- coding: utf-8 -*-
from __future__ import division
import tensorflow as tf
import random, os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from tensorflow.examples.tutorials.mnist import input_data
from sklearn.model_selection import train_test_split
from skimage import io, transform, util
import skimage
import argparse

# parse cli arguments
ap = argparse.ArgumentParser(description="Tensorflow RNN for text generation")
ap.add_argument('-t', '--train', help = 'Set this flag to train the RNN from scratch', action='store_true', default=False)
ap.add_argument('-t2', '--train2', help = 'Set this flag to train the RNN from the last point', action='store_true', default=False)
ap.add_argument('-c', '--clf', help = 'The file path for the image to be classified', default='')
args = vars(ap.parse_args())
isTrainingPhase = args['train']
isContinuingTraining = args['train2']
query_file_path = args['clf']

IMAGE_DIMS = (96, 96, 3)
HEIGHT = 96
WIDTH = 96
CHANNELS = 3
N_CLASSES = 5
TARGETS = ['bulbasaur', 'charmander', 'squirtle', 'pikachu', 'mewtwo']

EPOCHS = 100
LEARNING_RATE = 1e-3
BATCH_SIZE = 32

class PokemonDataset(object):
    def __init__(self, path='dataset'):
        # initialize the data and labels
        self.images = []
        self.labels = []

        # grab the image paths and randomly shuffle them
        image_paths = []
        for subdir, dirs, files in os.walk(path):
            for filename in files:
                if filename.endswith(".png") or filename.endswith(".jpg"):
                    image_paths.append(os.path.join(subdir, filename))

        # Seeding with the same value will give you the same random permutation
        # everytime. Take this out for real shuffle
        random.seed(42)
        random.shuffle(image_paths)
        print('[LOADED {} IMAGES]'.format(len(image_paths)))

        # loop over the input images to properly vectorize them and store labels
        for path in image_paths[:1161]:
            img = io.imread(image_paths[0])
            img_resized = transform.resize(img, IMAGE_DIMS)
            self.images.append(img_resized)

            label = path.split(os.path.sep)[-2]
            label_vec = np.zeros(N_CLASSES)
            label_vec[TARGETS.index('squirtle')] = 1
            self.labels.append(label_vec)

        # scale the raw pixel intensities to the range [0, 1]
        self.images = np.array(self.images, dtype="float") / 255.0
        self.labels = np.array(self.labels)

        # partition the data into training and testing splits using 80% of
        # the data for training and the remaining 20% for testing
        self.trainX, self.testX, self.trainY, self.testY = train_test_split(self.images,
        	self.labels, test_size=0.2, random_state=42)

        self.data_index = 0

    def next_batch_train(self, batch_size):
        batch_x = np.zeros((batch_size, HEIGHT, WIDTH, CHANNELS),dtype=np.float32)
        batch_y = np.zeros((batch_size, N_CLASSES),dtype=np.float32)

        if self.data_index + batch_size >= len(self.trainX):
            self.data_index = 0

        #print("FETCHING BATCH FOR IMAGES {} - {}..".format(self.data_index+1, self.data_index + batch_size))

        vec_idx = 0
        for i in range(self.data_index,self.data_index+batch_size):
            batch_x[vec_idx] = self.trainX[i]
            batch_y[vec_idx] = self.trainY[i]

        self.data_index = (self.data_index + batch_size) % len(self.trainX)

        return batch_x,batch_y

    def next_batch_test(self, batch_size):
        batch_x = np.zeros((batch_size, HEIGHT, WIDTH, CHANNELS),dtype=np.float32)
        batch_y = np.zeros((batch_size, N_CLASSES),dtype=np.float32)

        if self.data_index + batch_size >= len(self.testX):
            self.data_index = 0

        #print("FETCHING BATCH FOR IMAGES {} - {}..".format(self.data_index+1, self.data_index + batch_size))

        vec_idx = 0
        for i in range(self.data_index,self.data_index+batch_size):
            batch_x[vec_idx] = self.testX[i]
            batch_y[vec_idx] = self.testY[i]

        self.data_index = (self.data_index + batch_size) % len(self.testX)

        return batch_x,batch_y

    def size(self):
        return len(self.images)

def conv2d(x, W):
 return tf.nn.conv2d(x, W, strides=[1,1,1,1], padding='VALID')

# tf Graph input. None means that the first dimension can be of any size so it represents the batch size
x = tf.placeholder("float", [None, HEIGHT, WIDTH, CHANNELS])
y_ = tf.placeholder("float", [None, N_CLASSES])
keep_prob = tf.placeholder(tf.float32)

# The first weight tensor has a shape of [5, 5, 1, 32] because our filter is of size
# 5 x 5 (pretty standard). We only have one channel for grayscale and it's a 2D
# convolution. The final value, 32, is the number of output channels that we
# have - the number of features or feature maps that will be produced from this
# convolution. Basically, a 5 x 5 x 32 tensor will be outputted from this
# convolutional layer that will be inputted to the next one
#
# 3rd layer, we have a fully connected layer with 1024 neurons
weights = {
    'w1': tf.Variable(tf.truncated_normal([3,3,3,32], stddev=0.1)),
    'w2': tf.Variable(tf.truncated_normal([3,3,32,64], stddev=0.1)),
    'w3': tf.Variable(tf.truncated_normal([3,3,64,64], stddev=0.1)),
    'w4': tf.Variable(tf.truncated_normal([2,2,64,128], stddev=0.1)),
    'w5': tf.Variable(tf.truncated_normal([2,2,128,128], stddev=0.1)),
    'w6': tf.Variable(tf.truncated_normal([5*5*128,1024], stddev=0.1)),# output of previous layer should be 7*7 image with 64 channels so flatten in final layer by multipling
    'w7': tf.Variable(tf.truncated_normal([1024,5], stddev=0.1))
}

# We also create our bias variable with a component for each output channel.
biases = {
    'b1': tf.Variable(tf.constant(0.1, shape=[32])),
    'b2': tf.Variable(tf.constant(0.1, shape=[64])),
    'b3': tf.Variable(tf.constant(0.1, shape=[64])),
    'b4': tf.Variable(tf.constant(0.1, shape=[128])),
    'b5': tf.Variable(tf.constant(0.1, shape=[128])),
    'b6': tf.Variable(tf.constant(0.1, shape=[1024])),
    'b7': tf.Variable(tf.constant(0.1, shape=[5])),
}

# 'Saver' op to save and restore all the variables
saver = tf.train.Saver()

# Apply convolution to image (1st conv layer)
h_conv1 = conv2d(x, weights['w1']) + biases['b1']
print(h_conv1)

# Apply ReLU to image and pool (1st Pooling layer)
h_conv1 = tf.nn.relu(h_conv1)
h_pool1 = tf.layers.max_pooling2d(h_conv1, (3,3),3)

# Add dropout
h_pool1_drop = tf.nn.dropout(h_pool1, 0.25)
print(h_pool1_drop)

# Apply convolution and relu to image (2nd conv layer and 3rd conv layer):
# (CONV => RELU) * 2 => POOL
h_conv2 = tf.nn.relu(conv2d(h_pool1_drop, weights['w2']) + biases['b2'])
print(h_conv2)
h_conv3 = tf.nn.relu(conv2d(h_conv2, weights['w3']) + biases['b3'])
print(h_conv3)
h_pool3 = tf.layers.max_pooling2d(h_conv3, (2,2),2)
print(h_pool3)

# Add dropout
h_pool3_drop = tf.nn.dropout(h_pool3, 0.25)

# another set of   (CONV => RELU) * 2 => POOL
h_conv4 = tf.nn.relu(conv2d(h_pool3_drop, weights['w4']) + biases['b4'])
print(h_conv4)
h_conv5 = tf.nn.relu(conv2d(h_conv4, weights['w5']) + biases['b5'])
print(h_conv5)
h_pool6 = tf.layers.max_pooling2d(h_conv5, (2,2),2)
print(h_pool6)

# Add dropout
h_pool6_drop = tf.nn.dropout(h_pool6, 0.25)

# Fully connected layer
print(h_pool6_drop)
h_pool7_flat = tf.reshape(h_pool6_drop, [-1, 5*5*128]) # flatten
h_fc1 = tf.nn.relu(tf.matmul(h_pool7_flat, weights['w6']) + biases['b6']) # apply weights
h_fc1_drop = tf.nn.dropout(h_fc1, 0.5)

# Final, softmax layer
pred = tf.matmul(h_fc1_drop, weights['w7']) + biases['b7']
pred_probs = tf.nn.softmax(pred)

cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=pred, labels=y_))

#cost = tf.reduce_mean(-tf.reduce_sum(y_ * tf.log(y_conv), reduction_indices=[1])) # cross-entropy
optimizer = tf.train.AdamOptimizer(LEARNING_RATE).minimize(cost)
correct_prediction = tf.equal(tf.argmax(pred,1), tf.argmax(y_,1))
accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

init = tf.global_variables_initializer()

with tf.Session() as sess:
    sess.run(init)

    if(isTrainingPhase):
        ds = PokemonDataset()
        for epoch in range(EPOCHS):
            total_cost = 0
            num_batches = int(ds.size()/BATCH_SIZE)
            for i in range(num_batches):
                batch_x, batch_y = ds.next_batch_train(BATCH_SIZE)
                c = sess.run(cost, feed_dict={x: batch_x, y_: batch_y})
                sess.run(optimizer, feed_dict={x: batch_x, y_: batch_y})
                total_cost += c
            avg_cost = total_cost/num_batches
            print "Epoch:", (epoch+1), "cost =", "{:.5f}".format(avg_cost)
            if(epoch % 5 == 0):
                batch_x, batch_y = ds.next_batch_test(BATCH_SIZE)
                acc = sess.run(accuracy, feed_dict={x: batch_x, y_: batch_y})
                print "Test Accuracy: ", "{:.5f}".format(acc)
        print "\nTraining complete!"

        save_path = saver.save(sess, "Serial/dex-model")
        print("Model saved in file: %s" % save_path)
    elif(isContinuingTraining):
        ds = PokemonDataset()
        for epoch in range(EPOCHS):
            total_cost = 0
            num_batches = int(ds.size()/BATCH_SIZE)
            for i in range(num_batches):
                batch_x, batch_y = ds.next_batch_train(BATCH_SIZE)
                c = sess.run(cost, feed_dict={x: batch_x, y_: batch_y})
                sess.run(optimizer, feed_dict={x: batch_x, y_: batch_y})
                total_cost += c
            avg_cost = total_cost/num_batches
            print "Epoch:", (epoch+1), "cost =", "{:.5f}".format(avg_cost)
            if(epoch % 5 == 0):
                batch_x, batch_y = ds.next_batch_test(BATCH_SIZE)
                acc = sess.run(accuracy, feed_dict={x: batch_x, y_: batch_y})
                print "Test Accuracy: ", "{:.5f}".format(acc)
        print "\nTraining complete!"

        save_path = saver.save(sess, "Serial/dex-model")
        print("Model saved in file: %s" % save_path)
    elif(not query_file_path == ''):
        # Load test image
        images = []
        img = io.imread(query_file_path)
        img_resized = transform.resize(img, IMAGE_DIMS)
        images.append(img_resized)
        # scale the raw pixel intensities to the range [0, 1]
        images = np.array(images, dtype="float") / 255.0

        # Restore model weights from previously saved model
        model_path = "Serial/dex-model"
        saver.restore(sess, model_path)
        print("Model restored from file: %s" % model_path)
        y_pred = sess.run(pred_probs, feed_dict={x: images})
        prediction = tf.squeeze(y_pred) # convert prediction to single vector as in [vocab_size] instead of [1 x vocab_size]
        predicted_idx = sess.run(tf.argmax(prediction))
        print("{} ({}%)".format(TARGETS[predicted_idx], sess.run(prediction[predicted_idx])))
    else:
        print("[PLEASE PROVIDE A FLAG TO SPECIFY WHICH MODE TO RUN THE "\
                "SCRIPT. SEE --help FOR MORE INFO.]")


# img = io.imread(image_paths[0])
# img_resized = transform.resize(img, IMAGE_DIMS)
# #io.imsave('h.jpg', img_resized)
# print(np.shape(img_resized))
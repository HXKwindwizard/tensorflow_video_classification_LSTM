from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf


class C3D(object):
  """Builds the C3D network.

  Implements the inference pattern for model building.
  inference_c3d(): Builds the model as far as is required for running the network
  forward to make predictions.

  Args:
    _inputs: Size: [batch_size, num_steps, height, width, channels]
    _dropout: Float, the probability to keep the ValueError
    batch_size: Integer
    _weights: Dictionary, cotains all the weight variables
    _biases: Dictionary, contains all the bias variables
  """

  def __init__(self, _inputs, _dropout, batch_size, _weights, _biases):
    # Convolution Layer
    conv1 = _conv3d('conv1', _inputs, _weights['wc1'], _biases['bc1'])
    conv1 = tf.nn.relu(conv1, 'relu1')
    pool1 = _max_pool('pool1', conv1, k=1)

    # Convolution Layer
    conv2 = _conv3d('conv2', pool1, _weights['wc2'], _biases['bc2'])
    conv2 = tf.nn.relu(conv2, 'relu2')
    pool2 = _max_pool('pool2', conv2, k=2)

    # Convolution Layer
    conv3 = _conv3d('conv3a', pool2, _weights['wc3a'], _biases['bc3a'])
    conv3 = tf.nn.relu(conv3, 'relu3a')
    conv3 = _conv3d('conv3b', conv3, _weights['wc3b'], _biases['bc3b'])
    conv3 = tf.nn.relu(conv3, 'relu3b')
    pool3 = _max_pool('pool3', conv3, k=2)

    # Convolution Layer
    conv4 = _conv3d('conv4a', pool3, _weights['wc4a'], _biases['bc4a'])
    conv4 = tf.nn.relu(conv4, 'relu4a')
    conv4 = _conv3d('conv4b', conv4, _weights['wc4b'], _biases['bc4b'])
    conv4 = tf.nn.relu(conv4, 'relu4b')
    pool4 = _max_pool('pool4', conv4, k=2)

    # Convolution Layer
    conv5 = _conv3d('conv5a', pool4, _weights['wc5a'], _biases['bc5a'])
    conv5 = tf.nn.relu(conv5, 'relu5a')
    conv5 = _conv3d('conv5b', conv5, _weights['wc5b'], _biases['bc5b'])
    conv5 = tf.nn.relu(conv5, 'relu5b')
    pool5 = _max_pool('pool5', conv5, k=2)

    # Fully connected layer
    pool5 = tf.transpose(pool5, perm=[0,1,4,2,3])
    # Reshape conv3 output to fit dense layer input
    dense1 = tf.reshape(pool5, [batch_size, 
                                _weights['wd1'].get_shape().as_list()[0]])
    # shape: [batch_size, wd1[1]]
    self._out = tf.matmul(dense1, _weights['wd1']) + _biases['bd1']

  @property
  def output(self):
    return self._out


def _conv3d(name, l_input, w, b):
  return tf.nn.bias_add(
          tf.nn.conv3d(l_input, w, strides=[1, 1, 1, 1, 1], padding='SAME'),
          b)


def _max_pool(name, l_input, k):
  return tf.nn.max_pool3d(l_input, ksize=[1, k, 2, 2, 1], 
                          strides=[1, k, 2, 2, 1], padding='SAME', name=name)
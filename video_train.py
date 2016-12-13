from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time
import tensorflow as tf
import numpy as np
from video_input import DataInput
from bilstm_model import BiLSTM
from c3d_model import C3D

FLAGS = tf.app.flags.FLAGS

def _variable_on_cpu(name, shape, initializer):
  #with tf.device('/cpu:%d' % cpu_id):
  with tf.device('/cpu:0'):
    var = tf.get_variable(name, shape, initializer=initializer)
  return var


def _variable_with_weight_decay(name, shape, stddev, wd):
  var = _variable_on_cpu(name, shape, tf.truncated_normal_initializer(stddev=stddev))
  if wd is not None:
    weight_decay = tf.mul(tf.nn.l2_loss(var), wd, name='weight_loss')
    tf.add_to_collection('losses', weight_decay)
  return var


def feature_extract(config, c3d_data):
  """Extarct video feature using c3d  
    Args:
      config: configuration setting, include the c3d weights and the biases
      c3d_data: Tensor, [batch_size, c3d_num_steps, height, width, channels]
    Return:
      output: Tensor, [batch_size, 4096]
  """
  with tf.variable_scope('C3d_var'):
    weights = {
            'wc1': _variable_with_weight_decay('wc1', [3, 3, 3, 3, 64], 0.04, 0.00),
            'wc2': _variable_with_weight_decay('wc2', [3, 3, 3, 64, 128], 0.04, 0.00),
            'wc3a': _variable_with_weight_decay('wc3a', [3, 3, 3, 128, 256], 0.04, 0.00),
            'wc3b': _variable_with_weight_decay('wc3b', [3, 3, 3, 256, 256], 0.04, 0.00),
            'wc4a': _variable_with_weight_decay('wc4a', [3, 3, 3, 256, 512], 0.04, 0.00),
            'wc4b': _variable_with_weight_decay('wc4b', [3, 3, 3, 512, 512], 0.04, 0.00),
            'wc5a': _variable_with_weight_decay('wc5a', [3, 3, 3, 512, 512], 0.04, 0.00),
            'wc5b': _variable_with_weight_decay('wc5b', [3, 3, 3, 512, 512], 0.04, 0.00),
            'wd1': _variable_with_weight_decay('wd1', [8192, 4096], 0.04, 0.001),
            }
    biases = {
            'bc1': _variable_with_weight_decay('bc1', [64], 0.04, 0.0),
            'bc2': _variable_with_weight_decay('bc2', [128], 0.04, 0.0),
            'bc3a': _variable_with_weight_decay('bc3a', [256], 0.04, 0.0),
            'bc3b': _variable_with_weight_decay('bc3b', [256], 0.04, 0.0),
            'bc4a': _variable_with_weight_decay('bc4a', [512], 0.04, 0.0),
            'bc4b': _variable_with_weight_decay('bc4b', [512], 0.04, 0.0),
            'bc5a': _variable_with_weight_decay('bc5a', [512], 0.04, 0.0),
            'bc5b': _variable_with_weight_decay('bc5b', [512], 0.04, 0.0),
            'bd1': _variable_with_weight_decay('bd1', [4096], 0.04, 0.0),
            }
  c3d_model = C3D(c3d_data, config.keep_prob, config.batch_size, weights, biases)
  tf.get_variable_scope().reuse_variables()
  return c3d_model.output


def run_epoch(session, model, eval_op=None, verbose=False):
  """Runs the model on the given data."""
  start_time = time.time()
  costs = 0.0
  iters = 0

  fetches = {
    "cost": model.cost,
    "accuracy": model.accuracy
  }
  if eval_op is not None:
    fetches["eval_op"] = eval_op

  for step in range(model.input.epoch_size):
    vals = session.run(fetches)
    cost = vals["cost"]
    accuracy = vals["accuracy"]

    costs += cost
    iters += model.input.num_steps

    if verbose and step % 10 == 9:
      print("accuracy: %.3f" % accuracy)
      print("%.3f -- perplexity: %.3f -- speed: %.0f vps" %
          (step * 1.0 / model.input.epoch_size,
           np.exp(costs / iters),
           iters * model.input.batch_size / (time.time() - start_time)))

  return np.exp(costs / iters)


def train(config, data):
  """Video training procedure
    Args:
      config: the configuration class
      data: data class that implement the dataset.py interface
  """
  with tf.Graph().as_default():
    initializer = tf.random_uniform_initializer(-config.init_scale,
                                                config.init_scale)
    with tf.name_scope('Train'):
      train_input = DataInput(config=config, data=data)
        # c3d_intput: (num_steps/c3d_num_steps) * [batch_size, c3d_num_steps, height, width, channels]
      c3d_inputs = [clip for clip in tf.split(1, 
                                              config.num_steps/config.c3d_num_steps,
                                              train_input.input_data)]
      with tf.variable_scope('LSTM_Var', reuse=None, initializer=initializer):
        # bilstm_inputs: (num_steps/c3d_num_steps) * [batch_size, input_num(features)]
        train_input.input_data = [feature_extract(config, c3d_input) 
                                    for c3d_input in c3d_inputs] 
      model = BiLSTM(True, train_input, config, is_video=True)
      tf.scalar_summary("Training Loss", model.cost)
      tf.scalar_summary("Learning Rate", model.lr)

    sv = tf.train.Supervisor(logdir=FLAGS.save_path)
    with sv.managed_session() as session:
      for i in range(config.max_max_epoch):
        # Check if the one hot label is correct for corresponding image
        # a,b,c=session.run([train_input.filenames,train_input.labels,train_input.targets])
        # print("a:{} b:{} c:{}".format(a, b, c))

        lr_decay = config.lr_decay ** max(i - config.max_epoch, 0.0)
        model.assign_lr(session, config.learning_rate * lr_decay)
        print("Epoch: %d Learning rate: %.3f" %
            (i + 1, session.run(model.lr)))
        train_perplexity = run_epoch(session, model, eval_op=model.train_op,
                       verbose=True)

      if FLAGS.save_path:
        print("Saving model to %s." % FLAGS.save_path)
        sv.saver.save(session, FLAGS.save_path,
                global_step=sv.global_step)
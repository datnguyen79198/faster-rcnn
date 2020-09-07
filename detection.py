import tensorflow as tf
from tensorflow.keras import layers
from tensorflow.keras import backend as K

import utils

def detection_graph(rois,gt_ids,gt_boxes,config):
    #remove zero padding
    rois,_ = utils.remove_zero_padding(rois)
    gt_boxes,is_zeros = utils.remove_zero_padding(gt_boxes)
    gt_ids = tf.boolean_mask(gt_ids, is_zeros)

    #handle crowd
    # A crowd box in COCO is a bounding box around several instances. Exclude
    # them from training. A crowd box is given a negative class ID.
    crowd_ids = tf.where(gt_ids < 0)[:,0]
    non_crowd_ids = tf.where(gt_ids > 0)[:,0]
    crowd_gt_boxes = tf.gather(gt_boxes, crowd_ids)
    gt_ids = tf.gather(gt_ids, non_crowd_ids)
    gt_boxes = tf.gather(gt_boxes,non_crowd_ids)

    #compute IoU  between rois and crowd/non crowd GT boxes
    IoU_non_crowd = utils.IoU_overlap(rois,gt_boxes)
    IoU_crowd = utils.IoU_overlap(rois,crowd_gt_boxes)
    IoU_crowd_max = tf.reduce_max(IoU_crowd,axis=1)

    IoU_non_crowd_max = tf.reduce_max(IoU_non_crowd,axis=1)
    #positive rois
    positive_ids = tf.where(IoU_non_crowd_max >= 0.5)[:,0]
    #negative rois
    negative_ids = tf.where(tf.logical_and(IoU_non_crowd_max < 0.5, IoU_crowd_max < 0.001))[:,0]

    #subsample ROI. Aim for ratio positive/negative = 1/3
    positive_num = int(config.TRAIN_ROIS_PER_IMAGE * config.POSITIVE_ROI_RATIO)
    #positives
    positive_ids = tf.random_shuffle(positive_ids)[:positive_num]
    positive_num = tf.shape(positive_ids)[0]
    #negatives
    #num+ = r+ * all -> all = num+ / r+ num- = (1-r+)*all -> num- = (1-r+) * num+/r+ = 1/r+ * num+ - num+
    negative_ratio = 1.0 / config.POSITIVE_ROI_RATIO
    negative_num = tf.cast(negative_ratio * tf.cast(positive_num, tf.float32), tf.int32) - positive_num
    negative_ids = tf.random_shuffle(negative_ids)[:negative_num]



class DetectionLayer(layers.Layer):
    def __init__(self,config,**kwargs):
        super(ProposalLayer,self).__init__(**kwargs)
        self.config = config

    def call(self,input):
        rois = input[0]
        gt_ids = input[1]
        gt_boxes = input[2]

        output = utils.batch_slice([rois,gt_ids,gt_boxes], lambda x,y,z : detection_graph(x,y,z,self.config), self.config.IMAGES_PER_GPU)

        return output

    def compute_output_shape(self, input_shape):
        return (None,self.num_proposal,4)

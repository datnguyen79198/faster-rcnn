import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras import backend as K
import numpy as np
import math
#######customize########
import resnet101
import utils

class RCNN():
    def __init__(self,mode,config):
        self.mode = mode
        self.config = config #config hyperparameter
        self.anchor_cache = {} #dict
        self.model = self.build(mode=mode, config=config)

    def get_anchors(self,image_shape):

        backbone_shape = np.array([[int(math.ceil(image_shape[0]/stride)),int(math.ceil(image_shape[1]/stride))] for stride in self.config.BACKBONE_STRIDES])

        if not tuple(image_shape) in self.anchor_cache:
            anchors = utils.generate_anchors(self.config.ANCHOR_SCALES,
                                             self.config.ANCHOR_RATIOS,
                                             self.config.ANCHOR_STRIDE,
                                             backbone_shape,
                                             self.config.BACKBONE_STRIDES)

            self.anchor_cache[tuple(image_shape)] = utils.norm_boxes(anchors,image_shape[:2])

        return self.anchor_cache[tuple(image_shape)]

    def build(self,mode,config):
        h,w = config.IMAGE_SHAPE[:2]
        print(h,w)

        input_image = keras.Input(shape = [None,None,config.IMAGE_SHAPE[2]])

        #resnet layer
        C1,C2,C3,C4,C5 = resnet101.build_layers(input = input_image, config=config.TRAIN_BN)
        #FPN
        P2,P3,P4,P5,P6 = resnet101.build_FPN(C1=C1,C2=C2,C3=C3,C4=C4,C5=C5,config=config)

        RPN_feature = [P2,P3,P4,P5,P6]
        RCNN_feature = [P2,P3,P4,P5]


        if mode == "train":
            #RPN
            input_rpn_match = keras.Input(shape = [None,1], dtype=tf.int32) #match?
            input_rpn_bbox = keras.Input(shape = [None,4], dtype=tf.float32) #bounding box

            #ground truth
            input_gt_ids = keras.Input(shape = [None], dtype=tf.int32) #GT class IDs
            input_gt_boxes = keras.Input(shape = [None,4], dtype=tf.float32)

            #normalize ground truth boxes
            gt_boxes = layers.Lambda(lambda x : utils.norm_boxes(x,K.shape(input_image)[1:3]))(input_gt_boxes)

            #anchors for RPN
            anchors = self.get_anchors(config.IMAGE_SHAPE)

            anchors = layers.Lambda(lambda x : tf.Variable(anchors))(input_image)

        elif mode == "inference":
            #will do later
            x=1+1

        #RPN Keras model
        input_feature = keras.Input(shape=[None,None,config.PIRAMID_SIZE])

        """
        rpn_class_cls: anchor class classifier
        rpn_probs: anchor classifier probability
        rpn_bbox: anchor bounding box
        """
        outputs = RPN.build_graph(input_feature,len(config.ANCHOR_RATIOS),config.ANCHOR_STRIDE)

        RPN_model = keras.Model(inputs=[input_feature], outputs = outputs)

        """
        In FPN, we generate a pyramid of feature maps. We apply the RPN (described in the previous section)
        to generate ROIs. Based on the size of the ROI,
        we select the feature map layer in the most proper scale to extract the feature patches.
        """
        layer_outputs = []
        for x in RPN_feature:
            layer_outputs.append(RPN_model([x]))

        layer_outputs = list(zip(*layer_outputs))
        layer_outputs = [layers.Concatenate(axis=1)(list(o)) for o in layer_outputs]

        rpn_class_cls, rpn_probs, rpn_bbox = layer_outputs

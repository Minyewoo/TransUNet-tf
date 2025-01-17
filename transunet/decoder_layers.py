import tensorflow as tf
import tensorflow_addons as tfa

tfk = tf.keras
tfkl = tfk.layers
tfm = tf.math
L2_WEIGHT_DECAY = 1e-4


class SegmentationHead(tfkl.Layer):
    def __init__(self, name="seg_head",
                 num_classes=9,
                 kernel_size=1, 
                 final_act='sigmoid',
                 ** kwargs):
        tfkl.Layer.__init__(self, name=name, **kwargs)
        self.num_classes = num_classes
        self.kernel_size = kernel_size
        self.final_act  = final_act

    def build(self, input_shape):
        self.conv = tfkl.Conv2D(
            filters=self.num_classes, kernel_size=self.kernel_size, padding="same",
            kernel_regularizer=tfk.regularizers.L2(L2_WEIGHT_DECAY), 
            kernel_initializer=tfk.initializers.LecunNormal())
        self.act = tfkl.Activation(self.final_act)

    def call(self, inputs):
        x = self.conv(inputs)
        x = self.act(x)
        return x

    def get_config(self):
        config = super().get_config().copy()
        config.update({
            "num_classes": self.num_classes,
            "kernel_size": self.kernel_size,
            "final_act": self.final_act
        })
        return config


class Conv2DReLu(tfkl.Layer):
    def __init__(self, filters, kernel_size, padding="same", strides=1, **kwargs):
        tfkl.Layer.__init__(self, **kwargs)
        self.filters = filters
        self.kernel_size = kernel_size
        self.padding = padding
        self.strides = strides

    def build(self, input_shape):
        self.conv = tfkl.Conv2D(
            filters=self.filters, kernel_size=self.kernel_size, strides=self.strides,
            padding=self.padding, use_bias=False, kernel_regularizer=tfk.regularizers.L2(L2_WEIGHT_DECAY), 
            kernel_initializer="lecun_normal")

        self.bn = tfkl.BatchNormalization(momentum=0.9, epsilon=1e-5)

    def call(self, inputs):
        x = self.conv(inputs)
        x = self.bn(x)
        x = tf.nn.relu(x)
        return x

    def get_config(self):
        config = super().get_config().copy()
        config.update({
            "filters": self.filters,
            "kernel_size": self.kernel_size,
            "padding": self.padding,
            "strides": self.strides
        })
        return config


class DecoderBlock(tfkl.Layer):
    def __init__(self, filters, **kwargs):
        tfkl.Layer.__init__(self, **kwargs)
        self.filters = filters

    def build(self, input_shape):
        self.conv1 = Conv2DReLu(filters=self.filters, kernel_size=3)
        self.conv2 = Conv2DReLu(filters=self.filters, kernel_size=3)
        self.upsampling = tfkl.UpSampling2D(
            size=2, interpolation="bilinear")

    def call(self, inputs, skip=None):
        x = self.upsampling(inputs)
        if skip is not None:
            x = tf.concat([x, skip], axis=-1)
        x = self.conv1(x)
        x = self.conv2(x)
        return x

    def get_config(self):
        config = super().get_config().copy()
        config.update({
            "filters": self.filters,
        })
        return config

class DecoderCup(tfkl.Layer):
    def __init__(self, decoder_channels, n_skip=3, **kwargs):
        tfkl.Layer.__init__(self, **kwargs)
        self.decoder_channels = decoder_channels
        self.n_skip = n_skip

    def build(self, input_shape):
        self.conv_more = Conv2DReLu(filters=512, kernel_size=3)
        self.blocks = [DecoderBlock(filters=out_ch)
                       for out_ch in self.decoder_channels]

    def call(self, hidden_states, features):
        x = self.conv_more(hidden_states)
        for i, decoder_block in enumerate(self.blocks):
            if features is not None:
                skip = features[i] if (i < self.n_skip) else None
            else:
                skip = None
            x = decoder_block(x, skip=skip)
        return x

    def get_config(self):
        config = super().get_config().copy()
        config.update({
            "decoder_channels": self.decoder_channels,
            "n_skip": self.n_skip,
        })
        return config

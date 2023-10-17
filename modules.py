import torch
import torch.nn as nn
# from torch.utils.data import Dataset
# from torchvision import datasets
# from torchvision.transforms import ToTensor
# import matplotlib.pyplot as plt
from torch.autograd import Function
# from itertools import repeat
# import numpy as np
# import os
# import pandas as pd
# from torchvision.io import read_image

class ModifiedUNet(nn.Module):
	def __init__(self, in_channels, n_classes, base_n_filter = 8):
		super(ModifiedUNet, self).__init__()
		self.in_channels = in_channels
		self.n_classes = n_classes
		self.base_n_filter = base_n_filter

		self.lrelu = nn.LeakyReLU()
		self.Dropout2d = nn.Dropout2d(p=0.6)
		self.upsacle = nn.Upsample(scale_factor=2, mode='nearest')
		self.sigmoid = nn.Sigmoid()

		# Level 1 context pathway
		self.conv2d_c1_1 = nn.Conv2d(self.in_channels, self.base_n_filter, kernel_size=3, stride=1, padding=1, bias=False)
		self.conv2d_c1_2 = nn.Conv2d(self.base_n_filter, self.base_n_filter, kernel_size=3, stride=1, padding=1, bias=False)
		self.lrelu_conv_c1 = self.lrelu_conv(self.base_n_filter, self.base_n_filter)
		self.inorm2d_c1 = nn.InstanceNorm2d(self.base_n_filter)

		# Level 2 context pathway
		self.conv2d_c2 = nn.Conv2d(self.base_n_filter, self.base_n_filter*2, kernel_size=3, stride=2, padding=1, bias=False)
		self.norm_lrelu_conv_c2 = self.norm_lrelu_conv(self.base_n_filter*2, self.base_n_filter*2)
		self.inorm2d_c2 = nn.InstanceNorm2d(self.base_n_filter*2)

		# Level 3 context pathway
		self.conv2d_c3 = nn.Conv2d(self.base_n_filter*2, self.base_n_filter*4, kernel_size=3, stride=2, padding=1, bias=False)
		self.norm_lrelu_conv_c3 = self.norm_lrelu_conv(self.base_n_filter*4, self.base_n_filter*4)
		self.inorm2d_c3 = nn.InstanceNorm2d(self.base_n_filter*4)

		# Level 4 context pathway
		self.conv2d_c4 = nn.Conv2d(self.base_n_filter*4, self.base_n_filter*8, kernel_size=3, stride=2, padding=1, bias=False)
		self.norm_lrelu_conv_c4 = self.norm_lrelu_conv(self.base_n_filter*8, self.base_n_filter*8)
		self.inorm2d_c4 = nn.InstanceNorm2d(self.base_n_filter*8)

		# Level 5 context pathway, level 0 localization pathway
		self.conv2d_c5 = nn.Conv2d(self.base_n_filter*8, self.base_n_filter*16, kernel_size=3, stride=2, padding=1, bias=False)
		self.norm_lrelu_conv_c5 = self.norm_lrelu_conv(self.base_n_filter*16, self.base_n_filter*16)
		self.norm_lrelu_upscale_conv_norm_lrelu_l0 = self.norm_lrelu_upscale_conv_norm_lrelu(self.base_n_filter*16, self.base_n_filter*8)

		self.conv2d_l0 = nn.Conv2d(self.base_n_filter*8, self.base_n_filter*8, kernel_size = 1, stride=1, padding=0, bias=False)
		self.inorm2d_l0 = nn.InstanceNorm2d(self.base_n_filter*8)
            

		# Level 1 localization pathway
		self.conv_norm_lrelu_l1 = self.conv_norm_lrelu(self.base_n_filter*16, self.base_n_filter*16)
		self.conv2d_l1 = nn.Conv2d(self.base_n_filter*16, self.base_n_filter*8, kernel_size=1, stride=1, padding=0, bias=False)
		self.norm_lrelu_upscale_conv_norm_lrelu_l1 = self.norm_lrelu_upscale_conv_norm_lrelu(self.base_n_filter*8, self.base_n_filter*4)

		# Level 2 localization pathway
		self.conv_norm_lrelu_l2 = self.conv_norm_lrelu(self.base_n_filter*8, self.base_n_filter*8)
		self.conv2d_l2 = nn.Conv2d(self.base_n_filter*8, self.base_n_filter*4, kernel_size=1, stride=1, padding=0, bias=False)
		self.norm_lrelu_upscale_conv_norm_lrelu_l2 = self.norm_lrelu_upscale_conv_norm_lrelu(self.base_n_filter*4, self.base_n_filter*2)

		# Level 3 localization pathway
		self.conv_norm_lrelu_l3 = self.conv_norm_lrelu(self.base_n_filter*4, self.base_n_filter*4)
		self.conv2d_l3 = nn.Conv2d(self.base_n_filter*4, self.base_n_filter*2, kernel_size=1, stride=1, padding=0, bias=False)
		self.norm_lrelu_upscale_conv_norm_lrelu_l3 = self.norm_lrelu_upscale_conv_norm_lrelu(self.base_n_filter*2, self.base_n_filter)

		# Level 4 localization pathway
		self.conv_norm_lrelu_l4 = self.conv_norm_lrelu(self.base_n_filter*2, self.base_n_filter*2)
		self.conv2d_l4 = nn.Conv2d(self.base_n_filter*2, self.n_classes, kernel_size=1, stride=1, padding=0, bias=False)

		self.ds2_1x1_conv2d = nn.Conv2d(self.base_n_filter*8, self.n_classes, kernel_size=1, stride=1, padding=0, bias=False)
		self.ds3_1x1_conv2d = nn.Conv2d(self.base_n_filter*4, self.n_classes, kernel_size=1, stride=1, padding=0, bias=False)




	def conv_norm_lrelu(self, feat_in, feat_out):
		return nn.Sequential(
			nn.Conv2d(feat_in, feat_out, kernel_size=3, stride=1, padding=1, bias=False),
			nn.InstanceNorm2d(feat_out),
			nn.LeakyReLU())

	def norm_lrelu_conv(self, feat_in, feat_out):
		return nn.Sequential(
			nn.InstanceNorm2d(feat_in),
			nn.LeakyReLU(),
			nn.Conv2d(feat_in, feat_out, kernel_size=3, stride=1, padding=1, bias=False))

	def lrelu_conv(self, feat_in, feat_out):
		return nn.Sequential(
			nn.LeakyReLU(),
			nn.Conv2d(feat_in, feat_out, kernel_size=3, stride=1, padding=1, bias=False))

	def norm_lrelu_upscale_conv_norm_lrelu(self, feat_in, feat_out):
		return nn.Sequential(
			nn.InstanceNorm2d(feat_in),
			nn.LeakyReLU(),
			nn.Upsample(scale_factor=2, mode='nearest'),
			# should be feat_in*2 or feat_in
			nn.Conv2d(feat_in, feat_out, kernel_size=3, stride=1, padding=1, bias=False),
			nn.InstanceNorm2d(feat_out),
			nn.LeakyReLU())

	def forward(self, x):
		#  Level 1 context pathway
		out = self.conv2d_c1_1(x)
		residual_1 = out
		out = self.lrelu(out)
		out = self.conv2d_c1_2(out)
		out = self.Dropout2d(out)
		out = self.lrelu_conv_c1(out)
		# Element Wise Summation
		out += residual_1
		context_1 = self.lrelu(out)
		out = self.inorm2d_c1(out)
		out = self.lrelu(out)

		# Level 2 context pathway
		out = self.conv2d_c2(out)
		residual_2 = out
		out = self.norm_lrelu_conv_c2(out)
		out = self.Dropout2d(out)
		out = self.norm_lrelu_conv_c2(out)
		out += residual_2
		out = self.inorm2d_c2(out)
		out = self.lrelu(out)
		context_2 = out

		# Level 3 context pathway
		out = self.conv2d_c3(out)
		residual_3 = out
		out = self.norm_lrelu_conv_c3(out)
		out = self.Dropout2d(out)
		out = self.norm_lrelu_conv_c3(out)
		out += residual_3
		out = self.inorm2d_c3(out)
		out = self.lrelu(out)
		context_3 = out

		# Level 4 context pathway
		out = self.conv2d_c4(out)
		residual_4 = out
		out = self.norm_lrelu_conv_c4(out)
		out = self.Dropout2d(out)
		out = self.norm_lrelu_conv_c4(out)
		out += residual_4
		out = self.inorm2d_c4(out)
		out = self.lrelu(out)
		context_4 = out

		# Level 5
		out = self.conv2d_c5(out)
		residual_5 = out
		out = self.norm_lrelu_conv_c5(out)
		out = self.Dropout2d(out)
		out = self.norm_lrelu_conv_c5(out)
		out += residual_5
		out = self.norm_lrelu_upscale_conv_norm_lrelu_l0(out)

		out = self.conv2d_l0(out)
		out = self.inorm2d_l0(out)
		out = self.lrelu(out)
        
		# Level 1 localization pathway
		out = torch.cat([out, context_4], dim=1)
		out = self.conv_norm_lrelu_l1(out)
		out = self.conv2d_l1(out)
		out = self.norm_lrelu_upscale_conv_norm_lrelu_l1(out)

		# Level 2 localization pathway
		out = torch.cat([out, context_3], dim=1)
		out = self.conv_norm_lrelu_l2(out)
		ds2 = out #This is the skip
		out = self.conv2d_l2(out)
		out = self.norm_lrelu_upscale_conv_norm_lrelu_l2(out)

		# Level 3 localization pathway
		out = torch.cat([out, context_2], dim=1)
		out = self.conv_norm_lrelu_l3(out)
		ds3 = out #This is the skip
		out = self.conv2d_l3(out)
		out = self.norm_lrelu_upscale_conv_norm_lrelu_l3(out)

		# Level 4 localization pathway
		out = torch.cat([out, context_1], dim=1)
		out = self.conv_norm_lrelu_l4(out)
		out_pred = self.conv2d_l4(out)

		ds2_1x1_conv = self.ds2_1x1_conv2d(ds2)
		ds1_ds2_sum_upscale = self.upsacle(ds2_1x1_conv)
		ds3_1x1_conv = self.ds3_1x1_conv2d(ds3)
		ds1_ds2_sum_upscale_ds3_sum = ds1_ds2_sum_upscale + ds3_1x1_conv
		ds1_ds2_sum_upscale_ds3_sum_upscale = self.upsacle(ds1_ds2_sum_upscale_ds3_sum)

		out = out_pred + ds1_ds2_sum_upscale_ds3_sum_upscale
		seg_layer = out
		# out = out.permute(0, 2, 3, 1).contiguous().view(-1, self.n_classes)
		#out = out.view(-1, self.n_classes)
		out = self.sigmoid(out)
		return out, seg_layer

# 32 x 1 x 256 x 256 x 256
	
def dice_loss(y_true, y_pred, smooth=1e-5):
    intersection = torch.sum(y_true * y_pred, dim=(1,2,3))
    sum_of_squares_pred = torch.sum(torch.square(y_pred), dim=(1,2,3))
    sum_of_squares_true = torch.sum(torch.square(y_true), dim=(1,2,3))
    dice = 1 - (2 * intersection + smooth) / (sum_of_squares_pred + sum_of_squares_true + smooth)
    dice = torch.mean(dice)
    return dice
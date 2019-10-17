import torch
import numpy as np
import torchvision.transforms as transforms
from network_segmentation import VNet
from torch.autograd import Variable
import matplotlib.pyplot as plt
import numpy as np

class SegmentationNet():
    def __init__(self):
        torch.cuda.set_device(0)
        self.model_path = "./model_segmentation.pth.tar"
        self.model = VNet()
        self.model = self.model.cuda()
        self.model.load_state_dict(torch.load(self.model_path)['state_dict'])
        self.model.eval()
        print("loaded segmentation network")

    def segment(self, input_volume, show_results = True):
        segmentation_prior_air = 1
        segmentation_prior_soft = 1
        segmentation_prior_bone = 1

        mean = -630.1
        std=479.7
        blocksize = 128


        sanity_check_volume = np.zeros([3,input_volume.shape[0],input_volume.shape[1],input_volume.shape[2]])
        sanity_check_volume[0,:,:,:] = input_volume <= -700
        sanity_check_volume[1,:,:,:] = (input_volume <= 400) * (input_volume > -800)
        sanity_check_volume[2, :, :, :] = input_volume > 150

        blocks = np.ceil(np.array(input_volume.shape)/blocksize).astype(int)
        new_shape = blocks*blocksize
        offset_before = ((new_shape-input_volume.shape)//2).astype(int)
        offset_after = ((new_shape-input_volume.shape)-offset_before).astype(int)
        padded_volume = np.pad(input_volume,[[offset_before[0],offset_after[0]],[offset_before[1],offset_after[1]],[offset_before[2],offset_after[2]]],mode='edge')


        padded_volume -= mean
        padded_volume/= std

        segmented_volume = np.zeros([3, padded_volume.shape[0], padded_volume.shape[1], padded_volume.shape[2]],dtype=np.float32)
        print(segmented_volume.shape)
        counter  = 1
        for i in range(0,blocks[0]):
            for j in range(0,blocks[1]):
                for k in range(0,blocks[2]):
                    print(counter)
                    counter += 1
                    curren_block = padded_volume[i*blocksize:(i+1)*blocksize,j*blocksize:(j+1)*blocksize,k*blocksize:(k+1)*blocksize]
                    presegmentation = np.zeros((4, blocksize,blocksize,blocksize),dtype=np.float32)
                    presegmentation[0, :, :, :] = curren_block
                    presegmentation[1, :, :, :] = curren_block >= (200-mean)/std
                    presegmentation[2, :, :, :] = (curren_block < (200-mean)/std) * (curren_block >= (-500-mean)/std)
                    presegmentation[3, :, :, :] = curren_block < (-500-mean)/std
                    curren_block_tensor = torch.from_numpy(presegmentation).cuda()
                    curren_block_tensor = torch.unsqueeze(curren_block_tensor,0)
                    curren_block_tensor = curren_block_tensor.cpu()
                    tmp1 = Variable(curren_block_tensor,requires_grad = False)
                    tmp1cpu = tmp1.cpu()
                    tmp2 = self.model.forward(tmp1cpu)
                    output_tensor = np.array(tmp2.data)
                    segmented_volume[:,i*blocksize:(i+1)*blocksize,j*blocksize:(j+1)*blocksize,k*blocksize:(k+1)*blocksize] = output_tensor[0,:,:,:,:]
        segmented_volume = segmented_volume[:,offset_before[0]:input_volume.shape[0]+offset_before[0],offset_before[1]:input_volume.shape[1]+offset_before[1],offset_before[2]:input_volume.shape[2]+offset_before[2]]

        #ensure correct label
        segmented_volume *= sanity_check_volume
        segmented_volume[0,:,:,:] *= segmentation_prior_air
        segmented_volume[1, :, :, :] *= segmentation_prior_soft
        segmented_volume[2, :, :, :] *= segmentation_prior_bone
        segmented_volume = np.argmax(segmented_volume,axis=0)
        segmentation = {}

        # Air
        segmentation["air"] = segmented_volume == 0

        # Soft Tissue
        segmentation["soft tissue"] = segmented_volume == 1

        # Bone
        segmentation["bone"] = segmented_volume == 2

        if show_results:
            plt.figure()
            plt.imshow(segmented_volume[:,:,segmented_volume.shape[2]//2])
            plt.figure()
            plt.imshow(segmented_volume[:, segmented_volume.shape[1] // 2, :])
            plt.figure()
            plt.imshow(segmented_volume[ segmented_volume.shape[0] // 2, :,:])
            plt.show()

        return segmentation

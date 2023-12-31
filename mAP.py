import torch
from collections import Counter
import pandas as pd
from iou import intersection_over_union
import numpy as np


def mean_average_precision(
    pred_boxes, true_boxes, iou_threshold=0.5, box_format="midpoint", num_classes=20 , metric_df = False,
):
    """
    Calculates mean average precision 

    Parameters:
        pred_boxes (list): list of lists containing all bboxes with each bboxes
        specified as [train_idx, class_prediction, prob_score, x1, y1, x2, y2]
        true_boxes (list): Similar as pred_boxes except all the correct ones 
        iou_threshold (float): threshold where predicted bboxes is correct
        box_format (str): "midpoint" or "corners" used to specify bboxes
        num_classes (int): number of classes

    Returns:
        float: mAP value across all classes given a specific IoU threshold 
    """

    # list storing all AP for respective classes
    metric_dict = {}
    average_precisions = []
    wordname_15 = ['plane', 'baseball-diamond', 'bridge', 'ground-track-field', 'small-vehicle', 'large-vehicle', 'ship', 'tennis-court',
               'basketball-court', 'storage-tank',  'soccer-ball-field', 'roundabout', 'harbor', 'swimming-pool', 'helicopter','container-crane']
    confusion_metrics = {}
    img_m = 0
    for box in pred_boxes:
        if box[0] >0:
            img_m= box[0]

    img_metric_arr = np.zeros((img_m+1,3))
    
            
    # used for numerical stability later on
    epsilon = 1e-6

    for c in range(1,num_classes):

        detections = []
        ground_truths = []

        # Go through all predictions and targets,
        # and only add the ones that belong to the
        # current class c
        for detection in pred_boxes:
            if detection[1] == c:
                detections.append(detection)

        for true_box in true_boxes:
            if true_box[1] == c:
                ground_truths.append(true_box)

        # find the amount of bboxes for each training example
        # Counter here finds how many ground truth bboxes we get
        # for each training example, so let's say img 0 has 3,
        # img 1 has 5 then we will obtain a dictionary with:
        # amount_bboxes = {0:3, 1:5}
        amount_bboxes = Counter([gt[0] for gt in ground_truths])

        # We then go through each key, val in this dictionary
        # and convert to the following (w.r.t same example):
        # ammount_bboxes = {0:torch.tensor[0,0,0], 1:torch.tensor[0,0,0,0,0]}
        for key, val in amount_bboxes.items():
            amount_bboxes[key]  = torch.zeros(val)
            img_metric_arr[key][2] += val

        # sort by box probabilities which is index 2
        detections.sort(key=lambda x: x[2], reverse=True)
        TP = torch.zeros((len(detections)))
        FP = torch.zeros((len(detections)))
        total_true_bboxes = len(ground_truths)
        
        # If none exists for this class then we can safely skip
        if total_true_bboxes == 0:
            continue

        for detection_idx, detection in enumerate(detections):
            # Only take out the ground_truths that have the same
            # training idx as detection
            ground_truth_img = [
                bbox for bbox in ground_truths if bbox[0] == detection[0]
            ]

            num_gts = len(ground_truth_img)
            best_iou = 0

            for idx, gt in enumerate(ground_truth_img):
                iou = intersection_over_union(
                    torch.tensor(detection[3:]),
                    torch.tensor(gt[3:]),
                    box_format=box_format,
                )

                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = idx

            if best_iou > iou_threshold:
                # only detect ground truth detection once
                if amount_bboxes[detection[0]][best_gt_idx] == 0:
                    # true positive and add this bounding box to seen
                    TP[detection_idx] = 1
                    amount_bboxes[detection[0]][best_gt_idx] = 1
                    img_metric_arr[detection[0]][0]+=1
                else:
                    FP[detection_idx] = 1
                    img_metric_arr[detection[0]][1]+=1

            # if IOU is lower then the detection is a false positive
            else:
                FP[detection_idx] = 1
                img_metric_arr[detection[0]][1]+=1
        
        TP_cumsum = torch.cumsum(TP, dim=0)
        FP_cumsum = torch.cumsum(FP, dim=0)
        recalls = TP_cumsum / (total_true_bboxes + epsilon)
        precisions = TP_cumsum / (TP_cumsum + FP_cumsum + epsilon)

        metric_dict[wordname_15[c-1]] = [torch.sum(TP_cumsum == 1).item(), 
                                 torch.sum(FP_cumsum == 1).item(), 
                                 total_true_bboxes-torch.sum(TP == 1).item()]
        
        precisions = torch.cat((torch.tensor([1]), precisions))
        recalls = torch.cat((torch.tensor([0]), recalls))
        # torch.trapz for numerical integration
        average_precisions.append(torch.trapz(precisions, recalls))

        metric_dict[wordname_15[c-1]].append(sum(average_precisions)/len(average_precisions))
        print('class '+ wordname_15[c-1] +str(sum(average_precisions)/len(average_precisions)) )

    if metric_df:
        df_class_conf = pd.DataFrame.from_dict(metric_dict, orient='index', columns=['TP', 'FP', 'FN','AP'])
        df_class_conf["precision"] = df_class_conf['TP']/(df_class_conf['TP']+ df_class_conf['FP'] + epsilon)
        df_class_conf["recall"] = df_class_conf['TP']/(df_class_conf['TP']+ df_class_conf['FN'] + epsilon)
        df_imgs_conf = pd.DataFrame(img_metric_arr , columns=['TP', 'FP', 'GT'])
        df_imgs_conf["FN"] = df_imgs_conf["GT"] - df_imgs_conf["TP"]
        df_imgs_conf["precision"] = df_imgs_conf['TP']/(df_imgs_conf['TP']+ df_imgs_conf['FP'] + epsilon)
        df_imgs_conf["recall"]    = df_imgs_conf['TP']/(df_imgs_conf['TP']+ df_imgs_conf['FN'] + epsilon)
        return df_class_conf, df_imgs_conf, sum(average_precisions)/len(average_precisions)
        
    return sum(average_precisions)/len(average_precisions)

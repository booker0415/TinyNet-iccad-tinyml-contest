import numpy as np
import argparse
import pandas as pd
import torch
import torchvision.transforms as transforms
from torch.utils.data import DataLoader

from tqdm.auto import tqdm
from utils.help_code_demo import ToTensor, IEGM_DataSET, stats_report

parser = argparse.ArgumentParser()
# evaluation set-up params
parser.add_argument('--batch_size', type=int, default=1, help='batch size for inference')
parser.add_argument('--size', type=int, default=1250)
# data params
parser.add_argument('--path_data', type=str, default='/data/ICCAD22/tinyml_contest_data_training/')
# dataset with strengthened AFt
# parser.add_argument('--path_indices', type=str, default='/data/zhangmeng/chenh/Projects/tinyml2/iccad-tinyml-open-master3/iccad-tinyml-open-master/data_indices_gelei/')
# dataset with no strengthened AFt
parser.add_argument('--path_indices', type=str, default='./data_indices/')
# dataset of AFt or others
# parser.add_argument('--path_indices', type=str, default='/data/zhangmeng/chenh/Projects/tinyml2/iccad-tinyml-open-master3/iccad-tinyml-open-master/data_indices_gelei/AFt')
parser.add_argument('--mode', type=str, default='total', choices=['total', 'train', 'eval', 'test'],help="evaluation mode.")
parser.add_argument('--path_record', type=str, default='./records/')
# classifier hyperparams
parser.add_argument('--subset', type=int, default=1250)
parser.add_argument('--factor', type=float, default=2.1)
parser.add_argument('--thresh', type=float, default=9.2)
parser.add_argument('--method', type=str, default='interval')
parser.add_argument('--ensemble', action="store_true", help="ensemble pred")
# logger params
parser.add_argument('--track', action="store_true", help="Whether to enable experiment trackers for logging.")
parser.add_argument('--tqdm_', action="store_true", help="tqdm viz")
parser.add_argument('--verbose', action="store_true", help="Verbose mode")
parser.add_argument('--print_freq', type=int, default=0, help="print freq of perf data")
# instantiate
args = parser.parse_args()


def main():
    test_indice_path = args.path_indices + 'test_indice.csv'
    test_indices = pd.read_csv(test_indice_path)  # Adjust delimiter if necessary
    path_records = args.path_record
    subjects = test_indices['Filename'].apply(lambda x: x.split('-')[0]).unique().tolist()
    # List to store metrics for each participant
    subject_metrics = []
    device = torch.device('cuda:0')
    subjects_above_threshold = 0
    for subject_id in subjects:
        dataset = IEGM_DataSET(root_dir=args.path_data,
                               indice_dir=args.path_indices,
                               mode=args.mode,
                               size=args.size,
                               subject_id=subject_id,
                               transform=transforms.Compose([ToTensor()]))
        dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)

        method = args.method
        subset = args.subset
        tqdm_ = args.tqdm_

        # ensemble method: optionally define the decision boundaries
        if args.ensemble:
            factor = [1.5, 1.75, 2.0, 2.25, 2.5]
            # threshold = [9.191, 9.21, 9.263, 9.157, 9.154]
            threshold = [9.991, 10.21, 10.063, 9.957, 9.954]
        else:
            factor = [args.factor]
            threshold = [args.thresh]
        f1, fb, se, sp, bac, acc, ppv, npv = peak_based_eval(dataloader, factor, method, threshold, subset, tqdm_)
        f1 = round(f1, 5)
        fb = round(fb, 5)
        se = round(se, 5)
        sp = round(sp, 5)
        bac = round(bac, 5)
        acc = round(acc, 5)
        ppv = round(ppv, 5)
        npv = round(npv, 5)
        print("subject_id:", subject_id, "fb:", fb)
        subject_metrics.append([f1, fb, se, sp, bac, acc, ppv, npv])

        if fb > 0.95:
            subjects_above_threshold += 1
    subject_metrics_array = np.array(subject_metrics)

    # Calculate the mean values along the rows (subjects)
    average_metrics = np.mean(subject_metrics_array, axis=0)

    # Extract the individual average metric values

    avg_f1, avg_fb, avg_se, avg_sp, avg_bac, avg_acc, avg_ppv, avg_npv = average_metrics

    avg_f1 = round(avg_f1, 5)
    avg_fb = round(avg_fb, 5)
    avg_se = round(avg_se, 5)
    avg_sp = round(avg_sp, 5)
    avg_bac = round(avg_bac, 5)
    avg_acc = round(avg_acc, 5)
    avg_ppv = round(avg_ppv, 5)
    avg_npv = round(avg_npv, 5)
    # Print average metric values
    print("Final F-1:", avg_f1)
    print("Final F-B:", avg_fb)
    print("Final SEN:", avg_se)
    print("Final SPE:", avg_sp)
    print("Final BAC:", avg_bac)
    print("Final ACC:", avg_acc)
    print("Final PPV:", avg_ppv)
    print("Final NPV:", avg_npv)
    # Calculate the proportion of subjects above the threshold
    proportion_above_threshold = subjects_above_threshold / len(subjects)
    # The G score
    g_score = proportion_above_threshold
    # Print the G score
    print("G Score:", g_score)

    f = open(path_records + 'seg_stat.txt', 'a')
    f.write("Final F-B: {}\n".format(avg_fb))
    f.write("G Score: {}\n".format(g_score))
    f.close()


def reject_outliers(data, m=2.):
    '''
        reject outliers from the sampled peak intervals
        based on the variance away from the median value
    '''
    d = np.abs(data - np.median(data))
    mdev = np.median(d)
    s = d / mdev if mdev else 0.
    ans = data[s < m]
    if ans.ndim != 1:
        ans = np.squeeze(ans)
    return ans


def countPeaks(chunk, factor, method, inp_len=1250):
    '''
        sample the number of detected peaks for a given input and the peak sampling threshold factor
    '''
    # only look at the subset of the input
    chunk = chunk['IEGM_seg'].squeeze()
    chunk = chunk[:inp_len]

    # find standard deviation and mean of the input
    std, mean = torch.std_mean(chunk, unbiased=False)
    if args.verbose:
        print(f"\nstd: {std} mean: {mean}")

    # detect flag prevents over-sampling near the peaks
    detect = True
    delay_steps = 0
    peak_cnt = 0
    peak_sampled_idx = []
    # iterate through the input and count peaks
    for idx, val in enumerate(chunk):
        peak_threshold = std.item() * factor
        if val > peak_threshold:
            if detect:
                peak_sampled_idx.append(idx)
                peak_cnt += 1
                delay_steps = 0
                detect = False
        if not detect:
            delay_steps += 1
            if delay_steps > 20:
                detect = True
    # truncation works only when three or more peaks are sampled
    if len(peak_sampled_idx) < 3:
        return len(peak_sampled_idx)
    # baseline method
    og_ans = len(peak_sampled_idx)
    # truncation method
    peak_diff = np.diff(np.asarray(peak_sampled_idx))
    trunc_peak_diff = reject_outliers(peak_diff)
    trunc_ans = trunc_peak_diff.size + 1
    # interval method
    robustAvgInterval = sum(trunc_peak_diff) / trunc_peak_diff.size
    inter_ans = inp_len / robustAvgInterval
    if args.verbose:
        print('sampled peak indices: ', peak_sampled_idx)
        print(f'baseline ans: {og_ans} | truncated ans: {trunc_ans} | interval ans: {inter_ans}')
    return inter_ans


class PerformanceTracker(object):
    ''' Computes and stores the performance metrics '''

    def __init__(self, total):
        self.total = total
        self.reset()

    def reset(self):
        self.cnt_TP = 0
        self.cnt_FN = 0
        self.cnt_FP = 0
        self.cnt_TN = 0
        self.correct = 0
        self.running_total = 0

    def update(self, pred, label):
        if pred == label:
            self.correct += 1
            if label == 1:
                self.cnt_TP += 1
            else:
                self.cnt_TN += 1
        else:
            if label == 1:
                self.cnt_FN += 1
            else:
                self.cnt_FP += 1
        self.running_total += 1


def peak_based_eval(dataloader, factor, method, threshold_grid, subset=1250, tqdm_=False):
    f1_list, fb_list, se_list, sp_list, bac_list, acc_list, ppv_list, npv_list = [], [], [], [], [], [], [], []
    # print("*"*67)
    # print('threshold: ', threshold_grid)
    # print('factor: ', factor)
    # print(f'subset: {subset}')
    # print("-"*67)
    # calibrate threshold values if input is a subset of total len 1250
    if subset != 1250:
        threshold_grid *= subset / 1250
        print("calibrated threshold: ", threshold_grid)

    metrics = PerformanceTracker(len(dataloader))
    # print("analyzing...")
    for iter, data_val in enumerate(tqdm(dataloader) if tqdm_ else dataloader):
        label = data_val['label'].item()
        results = []
        va_pred_cnt = []
        for i in range(len(threshold_grid)):
            thresh = threshold_grid[i]
            factor_ = factor[i]
            numPeaks = countPeaks(data_val, factor_, method, subset)
            results.append(numPeaks)
            va_pred_cnt.append(numPeaks > thresh)
        if args.ensemble:
            # majority voting on ensemble results
            if np.count_nonzero(va_pred_cnt) > (len(factor) / 2 + 1):
                pred = 1
            else:
                pred = 0
        else:
            if numPeaks > thresh:
                pred = 1
            else:
                pred = 0

        if args.verbose:
            print(f'label: {label}', 'peaks sampled: ', numPeaks)

        metrics.update(pred, label)

        if args.print_freq > 0 and iter % args.print_freq == 0:
            print(f'running accuracy: {metrics.correct / metrics.running_total}')

    acc = metrics.correct / metrics.total
    # print('*'*65)
    # print('ensemble acc: ', acc)
    acc_list.append(round(acc, 5))
    f1, fb, se, sp, bac, acc, ppv, npv = stats_report([metrics.cnt_TP, metrics.cnt_FN, metrics.cnt_FP, metrics.cnt_TN])

    f1_list.append(f1)
    fb_list.append(fb)
    se_list.append(se)
    sp_list.append(sp)
    bac_list.append(bac)
    acc_list.append(acc)
    ppv_list.append(ppv)
    npv_list.append(npv)

    # print("\n")
    # print('threshold grid: ', threshold_grid)
    # print(f'std mult factor: {factor}')
    # print('acc: ', acc_list, 'best acc:', max(acc_list))
    # print(f'prec: {prec} | recall: {recall}')
    # print(f'f1: {f1} | fb: {fb}')
    return f1, fb, se, sp, bac, acc, ppv, npv


if __name__ == "__main__":
    main()

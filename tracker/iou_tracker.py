## https://github.com/bochinski/iou-tracker/blob/master/iou_tracker.py
## https://www.youtube.com/watch?v=JdzaKqXYlnM
import itertools
import numpy as np
import sys

sys.path.append('..')
from kalmanFilter import kf
from motionModel import constantVelocity


class VehicleTracker:

    def __init__(self):
        self.Ta = []
        self.Tf = []
        self.id = itertools.count(1)

    def track_iou(self, detections, time_stamp, sigma_iou, t_min):
        """
        Simple IOU based tracker.
        Ref. "High-Speed Tracking-by-Detection Without Using Image Information by E. Bochinski, V. Eiselein, T. Sikora" for
        more information. Kalman filter has been added by Harsh Nandan.
        Args:
             detections (list): list of detections per frame, usually generated by util.load_mot
             time_stamp (float): time stamp of current frame
             sigma_iou (float): IOU threshold.
             t_min (float): minimum track length in frames.
        Returns:
            list: list of tracks.
        """
        print(' ')
        print('Time stamp: ', time_stamp)
        for track_idx, track in enumerate(self.Ta):
            if len(detections) > 0:

                best_instant_iou = 0.
                if len(track['cg']) < 3:
                    iou_arr = np.zeros((detections.shape[0], 1))
                    for i in range(detections.shape[0]):
                        iou_arr[i] = self.iou(track['bboxes'][-1], detections[i])
                    best_instant_index = np.argmax(iou_arr)
                    best_instant_iou = iou_arr[best_instant_index]

                [print('detection', d) for d in detections]
                iou_arr_kf_predicted = np.zeros((detections.shape[0], 1))
                cg = track['kf'].predict_data_association(time_stamp)
                w = track['bboxes'][-1][2] - track['bboxes'][-1][0]
                h = track['bboxes'][-1][3] - track['bboxes'][-1][1]
                predicted_bbox = np.array([cg[0] - w / 2, cg[1] - h / 2, cg[0] + w / 2, cg[1] + h / 2], dtype=np.int32)
                track['predicted_box'].append(predicted_bbox)

                print('prediction bbox', predicted_bbox.transpose())

                for i in range(detections.shape[0]):
                    iou_arr_kf_predicted[i] = self.iou(predicted_bbox, detections[i])

                best_filtered_index = np.argmax(iou_arr_kf_predicted)
                best_filtered_iou = iou_arr_kf_predicted[best_filtered_index]

                if best_instant_iou > best_filtered_iou:
                    best_index = best_instant_index
                    best_iou = best_instant_iou
                else:
                    best_index = best_filtered_index
                    best_iou = best_filtered_iou

                best_box = detections[best_index]

                print('Best IOU:', best_iou, 'box associated:', best_box)

                if best_iou > sigma_iou:
                    best_match = best_box
                    cg = self.box_cg(best_match)
                    print('Cg of associated box', cg.transpose())

                    # update the state using predict as associated measurement has been found
                    track['kf'].predict(time_stamp)
                    # measurement update after data association
                    track['kf'].update(cg)

                    track['bboxes'].append(best_match)
                    track['cg'].append(cg)

                    self.Ta[track_idx] = track

                    # remove from best matching detection from detections
                    detections = np.delete(detections, best_index, axis=0)

        # create new tracks from left over detections
        if len(detections) > 0:
            print('------ starting new track ------ '.format('\n'))
            print('new detections', detections)
            new_tracks = [{'bboxes': [det],
                           'predicted_box': [np.array(det)],
                           'cg': [self.box_cg(det)],
                           'kf': kf.KalmanFilter(self.box_cg(det), time_stamp,
                                                 constantVelocity.ConstantVelocityModel(dims=2)),
                           'id': next(self.id)}
                          for det in detections]
            self.Ta += new_tracks

    def iou(self, bbox1, bbox2):
        """
        Calculates the intersection-over-union of two bounding boxes.
        Args:
            bbox1 (numpy.array, list of floats): bounding box in format x1,y1,x2,y2.
            bbox2 (numpy.array, list of floats): bounding box in format x1,y1,x2,y2.
        Returns:
            int: intersection-over-onion of bbox1, bbox2
        """

        bbox1 = [float(x) for x in bbox1]
        bbox2 = [float(x) for x in bbox2]

        (x0_1, y0_1, x1_1, y1_1) = bbox1
        (x0_2, y0_2, x1_2, y1_2) = bbox2

        # get the overlap rectangle
        overlap_x0 = max(x0_1, x0_2)
        overlap_y0 = max(y0_1, y0_2)
        overlap_x1 = min(x1_1, x1_2)
        overlap_y1 = min(y1_1, y1_2)

        # check if there is an overlap
        if overlap_x1 - overlap_x0 <= 0 or overlap_y1 - overlap_y0 <= 0:
            return 0

        # if yes, calculate the ratio of the overlap to each ROI size and the unified size
        size_1 = (x1_1 - x0_1) * (y1_1 - y0_1)
        size_2 = (x1_2 - x0_2) * (y1_2 - y0_2)
        size_intersection = (overlap_x1 - overlap_x0) * (overlap_y1 - overlap_y0)
        size_union = size_1 + size_2 - size_intersection

        return size_intersection / size_union

    def box_cg(self, box):
        return np.array([[(box[0] + box[2]) / 2], [(box[1] + box[3]) / 2]])

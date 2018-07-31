import os 
import sys
import time
import random
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
plt.style.use("ggplot")
from .meta_learner import MetaLearner, cosort_x

class NPLearner(MetaLearner):

    def __init__(self, session, parallel_models, optimize_op, train_set=None, eval_set=None, variables=None, lr=0.001, device_type='gpu', tags=["test"]):
        super().__init__(session, parallel_models, optimize_op, train_set, eval_set, variables, lr, device_type, tags)
        self.checkpoint_dir = "/data/ziz/jxu/neural_processes/" + self.save_dir
        self.result_dir = "results/neural_processes/" + self.save_dir
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)
        if not os.path.exists(self.result_dir):
            os.makedirs(self.result_dir)

    def visualise_1d(self, save_name):
        fig = plt.figure(figsize=(10, 10))
        for i in range(12):
            ax = fig.add_subplot(4, 3, i+1)
            sampler = self.eval_set.sample(1)[0]
            c = [1, 5, 10, 20]
            num_shots = c[(i%4)]
            X_value, y_value = sampler.sample(num_shots)
            X_c_value, X_t_value = X_value[:num_shots], X_value[num_shots:]
            y_c_value, y_t_value = y_value[:num_shots], y_value[num_shots:]
            m = self.parallel_models[0]
            X_gt, y_gt = sampler.get_all_samples()
            ax.plot(*cosort_x(X_gt[:,0], y_gt), "-")
            ax.scatter(X_c_value[:,0], y_c_value)

            for k in range(20):
                X_eval = np.linspace(self.eval_set.input_range[0], self.eval_set.input_range[1], num=100)[:,None]
                y_hat = m.predict(self.session, X_c_value, y_c_value, X_eval)
                ax.plot(X_eval[:,0], y_hat, "-", color='gray', alpha=0.5)

        fig.savefig(save_name)
        plt.close()


    def run_train(self, num_epoch, eval_interval, save_interval, eval_samples, meta_batch, num_shots, test_shots, load_params=False):
        saver = tf.train.Saver(var_list=self.variables)
        if load_params:
            ckpt_file = self.checkpoint_dir + '/params.ckpt'
            print('restoring parameters from', ckpt_file)
            saver.restore(self.session, ckpt_file)
        self.visualise_1d(os.path.join(self.result_dir, "{0}-{1}.pdf".format(self.eval_set.dataset_name, 0)))

        for epoch in range(1, num_epoch+1):
            self.qclock()
            for k in range(1000):
                self.train(meta_batch, num_shots, test_shots)
            train_time = self.qclock()
            print("Epoch {0}: {1:0.3f}s ...................".format(epoch, train_time))
            if epoch % eval_interval == 0:
                v = self.evaluate(eval_samples, num_shots, test_shots)
                print("    Eval Loss: ", v)
            if epoch % save_interval == 0:
                print("\tsave figure")
                self.visualise_1d(os.path.join(self.result_dir, "{0}-{1}.pdf".format(self.eval_set.dataset_name, epoch)))
                print("\tsave checkpoint")
                saver.save(self.session, self.checkpoint_dir + '/params.ckpt')
            sys.stdout.flush()

    def run_eval(self, num_func, num_shots, test_shots, step=1):
        saver = tf.train.Saver(var_list=self.variables)
        ckpt_file = self.checkpoint_dir + '/params.ckpt'
        print('restoring parameters from', ckpt_file)
        saver.restore(self.session, ckpt_file)
        m = self.parallel_models[0]
        evals = []
        for _ in range(num_func):
            sampler = self.eval_set.sample(1)[0]
            X_value, y_value = sampler.sample(num_shots+test_shots)
            X_c_value, X_t_value = X_value[:num_shots], X_value[num_shots:]
            y_c_value, y_t_value = y_value[:num_shots], y_value[num_shots:]
            l = m.compute_loss(self.get_session(), X_c_value, y_c_value, X_value, y_value, is_training=False, step=step)
            evals.append(l)
        eval = np.nanmean(evals)
        print(".......... EVAL : num_func {0} num_shots {1} test_shots {2} step {3} ............".format(num_func, num_shots, test_shots, step))
        print("\t{0}".format(eval))

        self.visualise_1d(os.path.join(self.result_dir, "{0}-{1}.pdf".format(self.eval_set.dataset_name, "eval")))

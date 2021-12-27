# !
#  * Copyright (c) Microsoft Corporation. All rights reserved.
#  * Licensed under the MIT License. See LICENSE file in the
#  * project root for license information.
from contextlib import contextmanager
from functools import partial
import signal
import os
from typing import Callable, List
import numpy as np
import time
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.ensemble import ExtraTreesRegressor, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier, DummyRegressor
from scipy.sparse import issparse
import logging
import shutil
from . import tune
from .data import (
    group_counts,
    CLASSIFICATION,
    TS_FORECAST,
    TS_TIMESTAMP_COL,
    TS_VALUE_COL,
    SEQCLASSIFICATION,
    SEQREGRESSION,
    QUESTIONANSWERING,
    SUMMARIZATION,
    NLG_TASKS)

import pandas as pd
from pandas import DataFrame, Series
import sys

try:
    import psutil
except ImportError:
    psutil = None
try:
    import resource
except ImportError:
    resource = None

logger = logging.getLogger("flaml.automl")
FREE_MEM_RATIO = 0.2


def TimeoutHandler(sig, frame):
    raise TimeoutError(sig, frame)


@contextmanager
def limit_resource(memory_limit, time_limit):
    if memory_limit > 0:
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if soft < 0 and (hard < 0 or memory_limit <= hard) or memory_limit < soft:
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, hard))
    main_thread = False
    if time_limit is not None:
        try:
            signal.signal(signal.SIGALRM, TimeoutHandler)
            signal.alarm(int(time_limit) or 1)
            main_thread = True
        except ValueError:
            pass
    try:
        yield
    finally:
        if main_thread:
            signal.alarm(0)
        if memory_limit > 0:
            resource.setrlimit(resource.RLIMIT_AS, (soft, hard))


class BaseEstimator:
    """The abstract class for all learners.

    Typical examples:
    * XGBoostEstimator: for regression.
    * XGBoostSklearnEstimator: for classification.
    * LGBMEstimator, RandomForestEstimator, LRL1Classifier, LRL2Classifier:
        for both regression and classification.
    """

    def __init__(self, task="binary", **config):
        """Constructor.

        Args:
            task: A string of the task type, one of
                'binary', 'multi', 'regression', 'rank', 'forecast'.
            config: A dictionary containing the hyperparameter names, 'n_jobs' as keys.
                n_jobs is the number of parallel threads.
        """
        self._task = task
        self.params = self.config2params(config)
        self.estimator_class = self._model = None
        if "_estimator_type" in config:
            self._estimator_type = self.params.pop("_estimator_type")
        else:
            self._estimator_type = (
                "classifier" if task in CLASSIFICATION else "regressor"
            )

    def get_params(self, deep=False):
        params = self.params.copy()
        params["task"] = self._task
        if hasattr(self, "_estimator_type"):
            params["_estimator_type"] = self._estimator_type
        return params

    @property
    def classes_(self):
        return self._model.classes_

    @property
    def n_features_in_(self):
        return self.model.n_features_in_

    @property
    def model(self):
        """Trained model after fit() is called, or None before fit() is called."""
        return self._model

    @property
    def estimator(self):
        """Trained model after fit() is called, or None before fit() is called."""
        return self._model

    def _preprocess(self, X):
        return X

    def _fit(self, X_train, y_train, **kwargs):

        current_time = time.time()
        if "groups" in kwargs:
            kwargs = kwargs.copy()
            groups = kwargs.pop("groups")
            if self._task == "rank":
                kwargs["group"] = group_counts(groups)
                # groups_val = kwargs.get('groups_val')
                # if groups_val is not None:
                #     kwargs['eval_group'] = [group_counts(groups_val)]
                #     kwargs['eval_set'] = [
                #         (kwargs['X_val'], kwargs['y_val'])]
                #     kwargs['verbose'] = False
                #     del kwargs['groups_val'], kwargs['X_val'], kwargs['y_val']
        X_train = self._preprocess(X_train)
        model = self.estimator_class(**self.params)
        if logger.level == logging.DEBUG:
            logger.debug(f"flaml.model - {model} fit started")
        model.fit(X_train, y_train, **kwargs)
        if logger.level == logging.DEBUG:
            logger.debug(f"flaml.model - {model} fit finished")
        train_time = time.time() - current_time
        self._model = model
        return train_time

    def fit(self, X_train, y_train, budget=None, **kwargs):
        """Train the model from given training data.

        Args:
            X_train: A numpy array or a dataframe of training data in shape n*m.
            y_train: A numpy array or a series of labels in shape n*1.
            budget: A float of the time budget in seconds.

        Returns:
            train_time: A float of the training time in seconds.
        """
        if (
            getattr(self, "limit_resource", None)
            and resource is not None
            and (budget is not None or psutil is not None)
        ):
            start_time = time.time()
            mem = psutil.virtual_memory() if psutil is not None else None
            try:
                with limit_resource(
                    mem.available * (1 - FREE_MEM_RATIO)
                    + psutil.Process(os.getpid()).memory_info().rss
                    if mem is not None
                    else -1,
                    budget,
                ):
                    train_time = self._fit(X_train, y_train, **kwargs)
            except (MemoryError, TimeoutError) as e:
                logger.warning(f"{e.__class__} {e}")
                if self._task in CLASSIFICATION:
                    model = DummyClassifier()
                else:
                    model = DummyRegressor()
                X_train = self._preprocess(X_train)
                model.fit(X_train, y_train)
                self._model = model
                train_time = time.time() - start_time
        else:
            train_time = self._fit(X_train, y_train, **kwargs)
        return train_time

    def predict(self, X_test):
        """Predict label from features.

        Args:
            X_test: A numpy array or a dataframe of featurized instances, shape n*m.

        Returns:
            A numpy array of shape n*1.
            Each element is the label for a instance.
        """
        if self._model is not None:
            X_test = self._preprocess(X_test)
            return self._model.predict(X_test)
        else:
            logger.warning(
                "Estimator is not fit yet. Please run fit() before predict()."
            )
            return np.ones(X_test.shape[0])

    def predict_proba(self, X_test):
        """Predict the probability of each class from features.

        Only works for classification problems

        Args:
            X_test: A numpy array of featurized instances, shape n*m.

        Returns:
            A numpy array of shape n*c. c is the # classes.
            Each element at (i,j) is the probability for instance i to be in
                class j.
        """
        assert self._task in CLASSIFICATION, "predict_proba() only for classification."

        X_test = self._preprocess(X_test)
        return self._model.predict_proba(X_test)

    def cleanup(self):
        del self._model
        self._model = None

    @classmethod
    def search_space(cls, data_size, task, **params):
        """[required method] search space.

        Args:
            data_size: A tuple of two integers, number of rows and columns.
            task: A str of the task type, e.g., "binary", "multi", "regression".

        Returns:
            A dictionary of the search space.
            Each key is the name of a hyperparameter, and value is a dict with
                its domain (required) and low_cost_init_value, init_value,
                cat_hp_cost (if applicable).
                e.g., ```{'domain': tune.randint(lower=1, upper=10), 'init_value': 1}```.
        """
        return {}

    @classmethod
    def size(cls, config: dict) -> float:
        """[optional method] memory size of the estimator in bytes.

        Args:
            config: A dict of the hyperparameter config.

        Returns:
            A float of the memory size required by the estimator to train the
            given config.
        """
        return 1.0

    @classmethod
    def cost_relative2lgbm(cls) -> float:
        """[optional method] relative cost compared to lightgbm."""
        return 1.0

    @classmethod
    def init(cls):
        """[optional method] initialize the class."""
        pass

    def config2params(self, config: dict) -> dict:
        """[optional method] config dict to params dict

        Args:
            config: A dict of the hyperparameter config.

        Returns:
            A dict that will be passed to self.estimator_class's constructor.
        """
        params = config.copy()
        return params


################# ADDED BY QSONG #################
class TransformersEstimator(BaseEstimator):
    """
    The base class for fine-tuning & distill model
    """
    ITER_HP = "global_max_steps" # NOTE: not sure if this should be included here

    def __init__(self, task="seq-classification", **config):
        super().__init__(task, **config)
        import uuid

        self.trial_id = str(uuid.uuid1().hex)[:8]
        if task in NLG_TASKS:
            from transformers import Seq2SeqTrainingArguments as TrainingArguments
        else:
            from transformers import TrainingArguments
        self._TrainingArguments = TrainingArguments

    def _join(self, X_train, y_train):
        y_train = DataFrame(y_train, columns=["label"], index=X_train.index)
        train_df = X_train.join(y_train)
        return train_df

    def search_space(cls, task, **params):
        search_space_dict = {
            "learning_rate": {
                "domain": tune.loguniform(lower=1e-6, upper=1e-3),
                "init_value": 1e-5,
            },
            "num_train_epochs": {
                "domain": tune.loguniform(lower=0.1, upper=10.0),
            },
            "per_device_train_batch_size": {
                "domain": tune.choice([4, 8, 16, 32]),
                "init_value": 32,
            },
            "warmup_ratio": {
                "domain": tune.uniform(lower=0.0, upper=0.3),
                "init_value": 0.0,
            },
            "weight_decay": {
                "domain": tune.uniform(lower=0.0, upper=0.3),
                "init_value": 0.0,
            },
            "adam_epsilon": {
                "domain": tune.loguniform(lower=1e-8, upper=1e-6),
                "init_value": 1e-6,
            },
            "seed": {"domain": tune.choice(list(range(40, 45))), "init_value": 42},
            "global_max_steps": {"domain": sys.maxsize, "init_value": sys.maxsize},
        }
        return search_space_dict

    def _init_hpo_args(self, automl_fit_kwargs: dict = None):
        from .nlp.utils import HPOArgs

        custom_hpo_args = HPOArgs()
        for key, val in automl_fit_kwargs["custom_hpo_args"].items():
            assert (
                key in custom_hpo_args.__dict__
            ), "The specified key {} is not in the argument list of flaml.nlp.utils::HPOArgs".format(
                key
            )
            setattr(custom_hpo_args, key, val)
        self.custom_hpo_args = custom_hpo_args

    def _preprocess(self, X, task, **kwargs):
        from .nlp.utils import tokenize_text

        if X.dtypes[0] == "string":
            return tokenize_text(X, task, self.custom_hpo_args)
        else:
            return X

    def _compute_metrics_by_dataset_name(self, eval_pred):
        from .ml import metric_loss_score

        predictions, labels = eval_pred
        predictions = (
            np.squeeze(predictions)
            if self._task == SEQREGRESSION
            else np.argmax(predictions, axis=1)
        )

        return {
            "val_loss": metric_loss_score(
                metric_name=self._metric_name, y_predict=predictions, y_true=labels
                )
            }
    
    def _delete_one_ckpt(self, ckpt_location):
            if self.use_ray is False:
                try:
                    shutil.rmtree(ckpt_location)
                except FileNotFoundError:
                    logger.warning("checkpoint {} not found".format(ckpt_location))

    def cleanup(self):
        super().cleanup()
        if hasattr(self, "_ckpt_remains"):
            for each_ckpt in self._ckpt_remains:
                self._delete_one_ckpt(each_ckpt)

    def _select_checkpoint(self, trainer):
        from transformers.trainer_utils import PREFIX_CHECKPOINT_DIR

        if trainer.ckpt_to_metric:
            best_ckpt, _ = min(
                trainer.ckpt_to_metric.items(), key=lambda x: x[1]["val_loss"]
            )
            best_ckpt_global_step = trainer.ckpt_to_global_step[best_ckpt]
            for each_ckpt in list(trainer.ckpt_to_metric):
                if each_ckpt != best_ckpt:
                    del trainer.ckpt_to_metric[each_ckpt]
                    del trainer.ckpt_to_global_step[each_ckpt]
                    self._delete_one_ckpt(each_ckpt)
        else:
            best_ckpt_global_step = trainer.state.global_step
            best_ckpt = os.path.join(
                trainer.args.output_dir,
                f"{PREFIX_CHECKPOINT_DIR}-{best_ckpt_global_step}",
            )
        self.params[self.ITER_HP] = best_ckpt_global_step
        print(trainer.state.global_step)
        print(trainer.ckpt_to_global_step)
        return best_ckpt


class DistiliingEstimator(TransformersEstimator):

    """
    The class for fine-tuning distill BERT model

    TODO: after completion, 
    modify ml.py by: adding import at L34, set estimator_class at L116
    """

    ITER_HP = "global_max_steps"

    from transformers import (
    WEIGHTS_NAME,
    AdamW,
    get_linear_schedule_with_warmup,
    squad_convert_examples_to_features,
    )

    def __init__(self, task="qa", **config):
        # import uuid
        super().__init__(task, **config)
        # self.trial_id = str(uuid.uuid1().hex)[:8]
        search_space_dict = super().search_space(task)
        if task == SEQREGRESSION:
            search_space_dict["alpha_mse"] =  {"domain": tune.uniform(lower=0.5, upper=1.0), "init_value": 0.5}
        else:
            search_space_dict["alpha_ce"] = {"domain":tune.uniform(lower=0.5, upper=1.0),"init_value": 0.5}

        search_space_dict["alpha_task"] = {"domain": tune.uniform(lower=0.5, upper=1.0), "init_value": 0.5}

            # TODO: the rests are for pretraining
            # "alpha_mlm": {"domain": tune.uniform(lower=0.0, upper=1.0),"init_value": 0.0}, # if mlm, use mlm over clm
            # "alpha_clm": {"domain": tune.uniform(lower=0.0, upper=1.0),"init_value": 0.5},
            # "alpha_cos": {"domain": tune.uniform(lower=0.0, upper=1.0), "init_value": 0.0},

    def _init_hpo_args(self, automl_fit_kwargs: dict = None):
        from .nlp.utils import DISTILHPOArgs,load_model
        # TODO: setup student and teacher seperatly,
        #  refer to: https://github.com/huggingface/transformers/blob/master/examples/research_projects/distillation/run_squad_w_distillation.py
        custom_hpo_args = DISTILHPOArgs()
        for key, val in automl_fit_kwargs["custom_hpo_args"].items():
            assert (
                    key in custom_hpo_args.__dict__
            ), "The specified key {} is not in the argument list of flaml.nlp.utils::DISTILHPOArgs".format(
                key
            )
            setattr(custom_hpo_args, key, val)
        self.custom_hpo_args = custom_hpo_args


    # def train(self,args,train_dataset, student, tokenizer, logger, teacher=None):
    #     """Train the model"""
    #     from torch.utils.data import DataLoader, RandomSampler
    #     from transformers.trainer_utils import set_seed
    #     from transformers import (
    #         AdamW,
    #         get_linear_schedule_with_warmup,
    #     )
    #     from tqdm import tqdm, trange
    #     import torch
    #     from torch import nn
    #     try:
    #         from torch.utils.tensorboard import SummaryWriter
    #     except ImportError:
    #         from tensorboardX import SummaryWriter
    #
    #     if args.local_rank in [-1, 0]:
    #         tb_writer = SummaryWriter()
    #
    #     args.train_batch_size = args.per_device_train_batch_size
    #     train_sampler = RandomSampler(train_dataset)
    #     train_dataloader = DataLoader(train_dataset, sampler=train_sampler, batch_size=args.train_batch_size)
    #
    #     if args.max_steps > 0:
    #         t_total = args.max_steps
    #         args.num_train_epochs = args.max_steps // (len(train_dataloader) // args.gradient_accumulation_steps) + 1
    #     else:
    #         t_total = len(train_dataloader) // args.gradient_accumulation_steps * args.num_train_epochs
    #
    #     # Prepare optimizer and schedule (linear warmup and decay)
    #     no_decay = ["bias", "LayerNorm.weight"]
    #     optimizer_grouped_parameters = [
    #         {
    #             "params": [p for n, p in student.named_parameters() if not any(nd in n for nd in no_decay)],
    #             "weight_decay": args.weight_decay,
    #         },
    #         {"params": [p for n, p in student.named_parameters() if any(nd in n for nd in no_decay)], "weight_decay": 0.0},
    #     ]
    #     optimizer = AdamW(optimizer_grouped_parameters, lr=args.learning_rate, eps=args.adam_epsilon)
    #     scheduler = get_linear_schedule_with_warmup(
    #         optimizer, num_warmup_steps=args.warmup_steps, num_training_steps=t_total
    #     )
    #
    #     # Check if saved optimizer or scheduler states exist
    #     if os.path.isfile(os.path.join(args.model_name_or_path, "optimizer.pt")) and os.path.isfile(
    #             os.path.join(args.model_name_or_path, "scheduler.pt")
    #     ):
    #         # Load in optimizer and scheduler states
    #         optimizer.load_state_dict(torch.load(os.path.join(args.model_name_or_path, "optimizer.pt")))
    #         scheduler.load_state_dict(torch.load(os.path.join(args.model_name_or_path, "scheduler.pt")))
    #
    #     if args.fp16:
    #         try:
    #             from apex import amp
    #         except ImportError:
    #             raise ImportError("Please install apex from https://www.github.com/nvidia/apex to use fp16 training.")
    #
    #         student, optimizer = amp.initialize(student, optimizer, opt_level=args.fp16_opt_level)
    #
    #     # # multi-gpu training (should be after apex fp16 initialization)
    #     # if args.n_gpu > 1:
    #     #     model = nn.DataParallel(model)
    #     #
    #     # # Distributed training (should be after apex fp16 initialization)
    #     # if args.local_rank != -1:
    #     #     model = nn.parallel.DistributedDataParallel(
    #     #         model, device_ids=[args.local_rank], output_device=args.local_rank, find_unused_parameters=True
    #     #     )
    #
    #     # Train!
    #     global_step = 1
    #     epochs_trained = 0
    #     steps_trained_in_current_epoch = 0
    #     # Check if continuing training from a checkpoint
    #     if os.path.exists(args.model_name_or_path):
    #         try:
    #             # set global_step to gobal_step of last saved checkpoint from model path
    #             checkpoint_suffix = args.model_name_or_path.split("-")[-1].split("/")[0]
    #             global_step = int(checkpoint_suffix)
    #             epochs_trained = global_step // (len(train_dataloader) // args.gradient_accumulation_steps)
    #             steps_trained_in_current_epoch = global_step % (len(train_dataloader) // args.gradient_accumulation_steps)
    #
    #             logger.info("  Continuing training from checkpoint, will skip to saved global_step")
    #             logger.info("  Continuing training from epoch %d", epochs_trained)
    #             logger.info("  Continuing training from global step %d", global_step)
    #             logger.info("  Will skip the first %d steps in the first epoch", steps_trained_in_current_epoch)
    #         except ValueError:
    #             logger.info("  Starting fine-tuning.")
    #
    #     tr_loss, logging_loss = 0.0, 0.0
    #     student.zero_grad()
    #     train_iterator = trange(
    #         epochs_trained, int(args.num_train_epochs), desc="Epoch", disable=args.local_rank not in [-1, 0]
    #     )
    #     # Added here for reproductibility
    #     set_seed(self.params.get("seed", args.seed))
    #
    #     for _ in train_iterator:
    #         epoch_iterator = tqdm(train_dataloader, desc="Iteration", disable=args.local_rank not in [-1, 0])
    #         for step, batch in enumerate(epoch_iterator):
    #
    #             # Skip past any already trained steps if resuming training
    #             if steps_trained_in_current_epoch > 0:
    #                 steps_trained_in_current_epoch -= 1
    #                 continue
    #
    #             student.train()
    #             if teacher is not None:
    #                 teacher.eval()
    #             batch = tuple(t.to(args.device) for t in batch)
    #
    #             inputs = {
    #                 "input_ids": batch[0],
    #                 "attention_mask": batch[1],
    #                 "start_positions": batch[3],
    #                 "end_positions": batch[4],
    #             }
    #             if args.student_type != "distilbert":
    #                 inputs["token_type_ids"] = None if args.student_type == "xlm" else batch[2]
    #             if args.student_type in ["xlnet", "xlm"]:
    #                 inputs.update({"cls_index": batch[5], "p_mask": batch[6]})
    #                 # if args.version_2_with_negative:
    #                 #     inputs.update({"is_impossible": batch[7]})
    #             outputs = student(**inputs)
    #             loss, start_logits_stu, end_logits_stu = outputs
    #
    #             # Distillation loss
    #             if teacher is not None:
    #                 if "token_type_ids" not in inputs:
    #                     inputs["token_type_ids"] = None if args.teacher_type == "xlm" else batch[2]
    #                 with torch.no_grad():
    #                     start_logits_tea, end_logits_tea = teacher(
    #                         input_ids=inputs["input_ids"],
    #                         token_type_ids=inputs["token_type_ids"],
    #                         attention_mask=inputs["attention_mask"],
    #                     )
    #                 assert start_logits_tea.size() == start_logits_stu.size()
    #                 assert end_logits_tea.size() == end_logits_stu.size()
    #
    #                 loss_fct = nn.KLDivLoss(reduction="batchmean")
    #                 loss_start = (
    #                         loss_fct(
    #                             nn.functional.log_softmax(start_logits_stu / args.temperature, dim=-1),
    #                             nn.functional.softmax(start_logits_tea / args.temperature, dim=-1),
    #                         )
    #                         * (args.temperature ** 2)
    #                 )
    #                 loss_end = (
    #                         loss_fct(
    #                             nn.functional.log_softmax(end_logits_stu / args.temperature, dim=-1),
    #                             nn.functional.softmax(end_logits_tea / args.temperature, dim=-1),
    #                         )
    #                         * (args.temperature ** 2)
    #                 )
    #                 loss_ce = (loss_start + loss_end) / 2.0
    #
    #                 loss = args.alpha_ce * loss_ce + args.alpha_task * loss
    #
    #             # if args.n_gpu > 1:
    #             #     loss = loss.mean()  # mean() to average on multi-gpu parallel (not distributed) training
    #             # if args.gradient_accumulation_steps > 1:
    #             #     loss = loss / args.gradient_accumulation_steps
    #
    #             if args.fp16:
    #                 with amp.scale_loss(loss, optimizer) as scaled_loss:
    #                     scaled_loss.backward()
    #             else:
    #                 loss.backward()
    #
    #             tr_loss += loss.item()
    #             if (step + 1) % args.gradient_accumulation_steps == 0:
    #                 if args.fp16:
    #                     nn.utils.clip_grad_norm_(amp.master_params(optimizer), args.max_grad_norm)
    #                 else:
    #                     nn.utils.clip_grad_norm_(student.parameters(), args.max_grad_norm)
    #
    #                 optimizer.step()
    #                 scheduler.step()  # Update learning rate schedule
    #                 student.zero_grad()
    #                 global_step += 1
    #
    #                 # Log metrics
    #                 if args.local_rank in [-1, 0] and args.logging_steps > 0 and global_step % args.logging_steps == 0:
    #                     # Only evaluate when single GPU otherwise metrics may not average well
    #                     # TODO: complete evaluate
    #                     if args.local_rank == -1 and args.evaluate_during_training:
    #                         results = self.evaluate(args, student, tokenizer,logger)
    #                         for key, value in results.items():
    #                             tb_writer.add_scalar("eval_{}".format(key), value, global_step)
    #                     tb_writer.add_scalar("lr", scheduler.get_lr()[0], global_step)
    #                     tb_writer.add_scalar("loss", (tr_loss - logging_loss) / args.logging_steps, global_step)
    #                     logging_loss = tr_loss
    #
    #                 if args.local_rank in [-1, 0] and args.save_steps > 0 and global_step % args.save_steps == 0:
    #                     # Save model checkpoint
    #                     output_dir = os.path.join(args.output_dir, "checkpoint-{}".format(global_step))
    #                     if not os.path.exists(output_dir):
    #                         os.makedirs(output_dir)
    #                     student_to_save = (
    #                         student.module if hasattr(student, "module") else student
    #                     )  # Take care of distributed/parallel training
    #                     student_to_save.save_pretrained(output_dir)
    #                     tokenizer.save_pretrained(output_dir)
    #
    #                     torch.save(args, os.path.join(output_dir, "training_args.bin"))
    #                     logger.info("Saving model checkpoint to %s", output_dir)
    #
    #                     torch.save(optimizer.state_dict(), os.path.join(output_dir, "optimizer.pt"))
    #                     torch.save(scheduler.state_dict(), os.path.join(output_dir, "scheduler.pt"))
    #                     logger.info("Saving optimizer and scheduler states to %s", output_dir)
    #
    #             if args.max_steps > 0 and global_step > args.max_steps:
    #                 epoch_iterator.close()
    #                 break
    #         if args.max_steps > 0 and global_step > args.max_steps:
    #             train_iterator.close()
    #             break
    #
    #     if args.local_rank in [-1, 0]:
    #         tb_writer.close()
    #
    #     return global_step, tr_loss / global_step
    #
    # def evaluate(self,args, model, tokenizer, logger, prefix=""):
    #     from torch.utils.data import DataLoader,SequentialSampler
    #     from tqdm import tqdm
    #     import torch
    #     # from torch import nn
    #     import timeit
    #     from transformers.data.metrics.squad_metrics import (
    #         compute_predictions_log_probs,
    #         compute_predictions_logits,
    #         squad_evaluate,
    #     )
    #     from transformers.data.processors.squad import SquadResult
    #
    #     dataset, examples, features = self.load_examples(args, tokenizer, evaluate=True, output_examples=True)
    #
    #     if not os.path.exists(args.output_dir) and args.local_rank in [-1, 0]:
    #         os.makedirs(args.output_dir)
    #
    #     args.eval_batch_size = args.per_device_eval_batch_size
    #
    #     # Note that DistributedSampler samples randomly
    #     eval_sampler = SequentialSampler(dataset)
    #     eval_dataloader = DataLoader(dataset, sampler=eval_sampler, batch_size=args.eval_batch_size)
    #
    #     # # multi-gpu evaluate
    #     # if args.n_gpu > 1 and not isinstance(model, nn.DataParallel):
    #     #     model = nn.DataParallel(model)
    #
    #     # Eval!
    #     logger.info("***** Running evaluation {} *****".format(prefix))
    #     logger.info("  Num examples = %d", len(dataset))
    #     logger.info("  Batch size = %d", args.eval_batch_size)
    #
    #     all_results = []
    #     start_time = timeit.default_timer()
    #
    #     for batch in tqdm(eval_dataloader, desc="Evaluating"):
    #         model.eval()
    #         batch = tuple(t.to(args.device) for t in batch)
    #
    #         with torch.no_grad():
    #             inputs = {"input_ids": batch[0], "attention_mask": batch[1]}
    #             if args.student_type != "distilbert":
    #                 inputs["token_type_ids"] = None if args.student_type == "xlm" else batch[2]  # XLM don't use segment_ids
    #             example_indices = batch[3]
    #             if args.student_type in ["xlnet", "xlm"]:
    #                 inputs.update({"cls_index": batch[4], "p_mask": batch[5]})
    #
    #             outputs = model(**inputs)
    #
    #         for i, example_index in enumerate(example_indices):
    #             eval_feature = features[example_index.item()]
    #             unique_id = int(eval_feature.unique_id)
    #
    #             output = [output[i].detach().cpu().tolist() for output in outputs]
    #
    #             # Some models (XLNet, XLM) use 5 arguments for their predictions, while the other "simpler"
    #             # models only use two.
    #             if len(output) >= 5:
    #                 start_logits = output[0]
    #                 start_top_index = output[1]
    #                 end_logits = output[2]
    #                 end_top_index = output[3]
    #                 cls_logits = output[4]
    #
    #                 result = SquadResult(
    #                     unique_id,
    #                     start_logits,
    #                     end_logits,
    #                     start_top_index=start_top_index,
    #                     end_top_index=end_top_index,
    #                     cls_logits=cls_logits,
    #                 )
    #
    #             else:
    #                 start_logits, end_logits = output
    #                 result = SquadResult(unique_id, start_logits, end_logits)
    #
    #             all_results.append(result)
    #
    #     evalTime = timeit.default_timer() - start_time
    #     logger.info("  Evaluation done in total %f secs (%f sec per example)", evalTime, evalTime / len(dataset))
    #
    #     # Compute predictions
    #     output_prediction_file = os.path.join(args.output_dir, "predictions_{}.json".format(prefix))
    #     output_nbest_file = os.path.join(args.output_dir, "nbest_predictions_{}.json".format(prefix))
    #
    #     if args.version_2_with_negative:
    #         output_null_log_odds_file = os.path.join(args.output_dir, "null_odds_{}.json".format(prefix))
    #     else:
    #         output_null_log_odds_file = None
    #
    #     if args.student_type in ["xlnet", "xlm"]:
    #         # XLNet uses a more complex post-processing procedure
    #         predictions = compute_predictions_log_probs(
    #             examples,
    #             features,
    #             all_results,
    #             args.n_best_size,
    #             args.max_answer_length,
    #             output_prediction_file,
    #             output_nbest_file,
    #             output_null_log_odds_file,
    #             model.config.start_n_top,
    #             model.config.end_n_top,
    #             args.version_2_with_negative,
    #             tokenizer,
    #             args.verbose_logging,
    #         )
    #     else:
    #         predictions = compute_predictions_logits(
    #             examples,
    #             features,
    #             all_results,
    #             args.n_best_size,
    #             args.max_answer_length,
    #             args.do_lower_case,
    #             output_prediction_file,
    #             output_nbest_file,
    #             output_null_log_odds_file,
    #             args.verbose_logging,
    #             args.version_2_with_negative,
    #             args.null_score_diff_threshold,
    #             tokenizer,
    #         )
    #
    #     # Compute the F1 and exact scores.
    #     results = squad_evaluate(examples, predictions)
    #     return results
    #
    # def load_examples(self,args, tokenizer, dataset, evaluate=False,output_examples=False):
    #     import torch
    #     from transformers import squad_convert_examples_to_features
    #     from transformers.data.processors.squad import SquadV1Processor, SquadV2Processor
    #
    #     # if args.local_rank not in [-1, 0] and not evaluate:
    #     #     # Make sure only the first process in distributed training process the dataset, and the others will use the cache
    #     #     # torch.distributed.barrier()
    #
    #     # dataset must be tensorflow_dataset.load('squad')
    #     processor = SquadV2Processor() if args.version_2_with_negative else SquadV1Processor()
    #     examples = processor.get_examples_from_dataset(dataset, evaluate=evaluate)
    #
    #     features, dataset = squad_convert_examples_to_features(
    #             examples=examples,
    #             tokenizer=tokenizer,
    #             max_seq_length=args.max_seq_length,
    #             doc_stride=args.doc_stride,
    #             max_query_length=args.max_query_length,
    #             is_training=not evaluate,
    #             return_dataset="pt",
    #             threads=args.threads,
    #         )
    #
    #     # if args.local_rank == 0 and not evaluate:
    #     #     # Make sure only the first process in distributed training process the dataset, and the others will use the cache
    #     #     torch.distributed.barrier()
    #
    #     if output_examples:
    #         return dataset, examples, features
    #     return dataset


    def fit(self,X_train: DataFrame, y_train: Series, budget=None, **kwargs):
        from transformers import EarlyStoppingCallback
        from datasets import Dataset
        from transformers.trainer_utils import set_seed
        from transformers import AutoTokenizer

        import transformers
        from .nlp.utils import (
            get_num_labels,
            separate_config,
            load_model,
            compute_checkpoint_freq,
            get_trial_fold_name,
            date_str,
        )

        # TODO: if self._task == QUESTIONANSWERING, uncomment the code below (add indentation before
        #  from .nlp.huggingface.trainer import TrainerForAuto)

        # if self._task in NLG_TASKS:
        #     from .nlp.huggingface.trainer import Seq2SeqTrainerForAuto as TrainerForAuto
        # else:
        from .nlp.huggingface.trainer import TrainerForAuto

        this_params = self.params

        class EarlyStoppingCallbackForAuto(EarlyStoppingCallback):
            def on_train_begin(self, args, state, control, **callback_kwargs):
                self.train_begin_time = time.time()

            def on_step_begin(self, args, state, control, **callback_kwargs):
                self.step_begin_time = time.time()

            def on_step_end(self, args, state, control, **callback_kwargs):
                if state.global_step == 1:
                    self.time_per_iter = time.time() - self.step_begin_time
                if (
                    budget
                    and (
                        time.time() + self.time_per_iter
                        > self.train_begin_time + budget
                    )
                    or state.global_step >= this_params[FineTuningEstimator.ITER_HP]
                ):
                    control.should_training_stop = True
                    control.should_save = True
                    control.should_evaluate = True
                return control

            def on_epoch_end(self, args, state, control, **callback_kwargs):
                if (
                    control.should_training_stop
                    or state.epoch + 1 >= args.num_train_epochs
                ):
                    control.should_save = True
                    control.should_evaluate = True

        set_seed(self.params.get("seed", self._TrainingArguments.seed))

        self._init_hpo_args(kwargs)
        self._metric_name = kwargs["metric"]
        if hasattr(self, "use_ray") is False:
            self.use_ray = kwargs["use_ray"]

        X_val = kwargs.get("X_val")
        y_val = kwargs.get("y_val")

        if self._task not in NLG_TASKS:
            X_train, _ = self._preprocess(X=X_train, task=self._task, **kwargs)
        else:
            X_train, y_train = self._preprocess(
                X=X_train, y=y_train, task=self._task, **kwargs
            )

        train_dataset = Dataset.from_pandas(self._join(X_train, y_train))

        # TODO: set a breakpoint here, observe the resulting train_dataset,
        #  compare it with the output of the tokenized results in your transformer example
        #  for example, if your task is MULTIPLECHOICE, you need to compare train_dataset with
        #  the output of https://github.com/huggingface/transformers/blob/master/examples/pytorch/multiple-choice/run_swag.py#L329
        #  make sure they are the same

        if X_val is not None:
            if self._task not in NLG_TASKS:
                X_val, _ = self._preprocess(X=X_val, task=self._task, **kwargs)
            else:
                X_val, y_val = self._preprocess(
                    X=X_val, y=y_val, task=self._task, **kwargs
                )
            eval_dataset = Dataset.from_pandas(self._join(X_val, y_val))
        else:
            eval_dataset = None


        # TODO: set a breakpoint here, observe the resulting train_dataset,
        #  compare it with the output of the tokenized results in your transformer example
        #  for example, if your task is MULTIPLECHOICE, you need to compare train_dataset with
        #  the output of https://github.com/huggingface/transformers/blob/master/examples/pytorch/multiple-choice/run_swag.py#L329
        #  make sure they are the same

        tokenizer = AutoTokenizer.from_pretrained(
            self.custom_hpo_args.tokenizer_name , use_fast=True
        )
        self._tokenizer = tokenizer

        num_labels = get_num_labels(self._task, y_train)

        training_args_config, per_model_config = separate_config(
            self.params, self._task
        )

        ckpt_freq = compute_checkpoint_freq(
            train_data_size=len(train_dataset),
            custom_hpo_args=self.custom_hpo_args,
            num_train_epochs=training_args_config.get(
                "num_train_epochs", self._TrainingArguments.num_train_epochs
            ),
            batch_size=training_args_config.get(
                "per_device_train_batch_size",
                self._TrainingArguments.per_device_train_batch_size,
            ),
        )

        local_dir = os.path.join(
            self.custom_hpo_args.output_dir, "train_{}".format(date_str())
        )

        if not self.use_ray:
            # if self.params = {}, don't include configuration in trial fold name
            trial_dir = get_trial_fold_name(local_dir, self.params, self.trial_id)
        else:
            import ray

            trial_dir = ray.tune.get_trial_dir()

        if transformers.__version__.startswith("3"):
            training_args = self._TrainingArguments(
                report_to=[],
                output_dir=trial_dir,
                do_train=True,
                do_eval=True,
                eval_steps=ckpt_freq,
                evaluate_during_training=True,
                save_steps=ckpt_freq,
                save_total_limit=0,
                fp16=self.custom_hpo_args.fp16,
                load_best_model_at_end=True,
                **training_args_config,
            )
        else:
            from transformers import IntervalStrategy
            training_args = self._TrainingArguments(
                report_to=[],
                output_dir=trial_dir,
                do_train=True,
                do_eval=True,
                per_device_eval_batch_size=1,
                eval_steps=ckpt_freq,
                evaluation_strategy=IntervalStrategy.STEPS,
                save_steps=ckpt_freq,
                save_total_limit=0,
                fp16=self.custom_hpo_args.fp16,
                load_best_model_at_end=True,
                **training_args_config,
            )

        # model_init
        self.student = load_model(
                checkpoint_path=self.custom_hpo_args.student_name_or_path,
                task=self._task,
                num_labels=None,
                per_model_config=per_model_config,
            )

        self.teacher = load_model(
                checkpoint_path=self.custom_hpo_args.teacher_name_or_path,
                task=self._task,
                num_labels=None,
            )

        self._model = TrainerForAuto(
            args=training_args,
            teacher=self.teacher,
            model_init=self.student,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=tokenizer,
            compute_metrics=self._compute_metrics_by_dataset_name,
            callbacks=[EarlyStoppingCallbackForAuto],
        )

        setattr(self._model, "_use_ray", self.use_ray)
        if self._task in NLG_TASKS:
            setattr(self._model, "_is_seq2seq", True)
        self._model.train()

        self.params[self.ITER_HP] = self._model.state.global_step
        self._checkpoint_path = self._select_checkpoint(self._model)

        self._kwargs = kwargs
        self._num_labels = num_labels
        self._per_model_config = per_model_config
        self._training_args_config = training_args_config

        self._ckpt_remains = list(self._model.ckpt_to_metric.keys())

    def _delete_one_ckpt(self, ckpt_location):
        if self.use_ray is False:
            try:
                shutil.rmtree(ckpt_location)
            except FileNotFoundError:
                logger.warning("checkpoint {} not found".format(ckpt_location))

    def cleanup(self):
        super().cleanup()
        if hasattr(self, "_ckpt_remains"):
            for each_ckpt in self._ckpt_remains:
                self._delete_one_ckpt(each_ckpt)

    def _select_checkpoint(self, trainer):
        from transformers.trainer_utils import PREFIX_CHECKPOINT_DIR

        if trainer.ckpt_to_metric:
            best_ckpt, _ = min(
                trainer.ckpt_to_metric.items(), key=lambda x: x[1]["val_loss"]
            )
            best_ckpt_global_step = trainer.ckpt_to_global_step[best_ckpt]
            for each_ckpt in list(trainer.ckpt_to_metric):
                if each_ckpt != best_ckpt:
                    del trainer.ckpt_to_metric[each_ckpt]
                    del trainer.ckpt_to_global_step[each_ckpt]
                    self._delete_one_ckpt(each_ckpt)
        else:
            best_ckpt_global_step = trainer.state.global_step
            best_ckpt = os.path.join(
                trainer.args.output_dir,
                f"{PREFIX_CHECKPOINT_DIR}-{best_ckpt_global_step}",
            )
        self.params[self.ITER_HP] = best_ckpt_global_step
        print(trainer.state.global_step)
        print(trainer.ckpt_to_global_step)
        return best_ckpt

    def _compute_metrics_by_dataset_name(self, eval_pred):
        from .ml import metric_loss_score
        from .nlp.utils import postprocess_text

        predictions, labels = eval_pred

        if self._task in NLG_TASKS:
            if isinstance(predictions, tuple):
                predictions = np.argmax(predictions[0], axis=2)
            decoded_preds = self._tokenizer.batch_decode(
                predictions, skip_special_tokens=True
            )
            labels = np.where(labels != -100, labels, self._tokenizer.pad_token_id)
            decoded_labels = self._tokenizer.batch_decode(
                labels, skip_special_tokens=True
            )
            predictions, labels = postprocess_text(decoded_preds, decoded_labels)
        else:
            predictions = (
                np.squeeze(predictions)
                if self._task == SEQREGRESSION
                else np.argmax(predictions, axis=1)
            )

        return {
            "val_loss": metric_loss_score(
                metric_name=self._metric_name, y_predict=predictions, y_true=labels
            )
        }

    def predict_proba(self, X_test):
        assert (
            self._task in CLASSIFICATION
        ), "predict_proba() only for classification tasks."

        from datasets import Dataset
        from .nlp.huggingface.trainer import TrainerForAuto
        from transformers import TrainingArguments
        from .nlp.utils import load_model

        X_test, _ = self._preprocess(X_test, task=self._task, **self._kwargs)
        test_dataset = Dataset.from_pandas(X_test)

        best_model = load_model(
            checkpoint_path=self._checkpoint_path,
            task=self._task,
            num_labels=self._num_labels,
            per_model_config=self._per_model_config,
        )
        training_args = TrainingArguments(
            per_device_eval_batch_size=1,
            output_dir=self.custom_hpo_args.output_dir,
        )
        self._model = TrainerForAuto(model=best_model, args=training_args)
        predictions = self._model.predict(test_dataset)
        return predictions.predictions

    def predict(self, X_test):
        from datasets import Dataset
        from .nlp.utils import load_model
        from .nlp.huggingface.trainer import TrainerForAuto

        X_test, _ = self._preprocess(X=X_test, task=self._task, **self._kwargs)
        test_dataset = Dataset.from_pandas(X_test)

        best_model = load_model(
            checkpoint_path=self._checkpoint_path,
            task=self._task,
            num_labels=self._num_labels,
            per_model_config=self._per_model_config,
        )
        training_args = self._TrainingArguments(
            per_device_eval_batch_size=1,
            output_dir=self.custom_hpo_args.output_dir,
            **self._training_args_config,
        )
        self._model = TrainerForAuto(model=best_model, args=training_args)
        if self._task not in NLG_TASKS:
            predictions = self._model.predict(test_dataset)
        else:
            predictions = self._model.predict(
                test_dataset,
                max_length=training_args.generation_max_length,
                num_beams=training_args.generation_num_beams,
            )

        if self._task == SEQCLASSIFICATION:
            return np.argmax(predictions.predictions, axis=1)
        elif self._task == SEQREGRESSION:
            return predictions.predictions
        # TODO: elif self._task == your task, return the corresponding prediction
        #  e.g., if your task == QUESTIONANSWERING, you need to return the answer instead
        #  of the index
        elif self._task == SUMMARIZATION:
            if isinstance(predictions.predictions, tuple):
                predictions = np.argmax(predictions.predictions[0], axis=2)
            decoded_preds = self._tokenizer.batch_decode(
                predictions, skip_special_tokens=True
            )
            return decoded_preds

    def config2params(self, config: dict) -> dict:
        params = config.copy()
        params[FineTuningEstimator.ITER_HP] = params.get(
            FineTuningEstimator.ITER_HP, sys.maxsize
        )
        return params

    
################# END ADDED BY QSONG #################

class FineTuningEstimator(TransformersEstimator):
    """The class for fine-tuning language models, using huggingface transformers API."""

    ITER_HP = "global_max_steps"

    def __init__(self, task="seq-classification", **config):
        super().__init__(task, **config)
        import uuid

        self.trial_id = str(uuid.uuid1().hex)[:8]
        if task in NLG_TASKS:
            from transformers import Seq2SeqTrainingArguments as TrainingArguments
        else:
            from transformers import TrainingArguments
        self._TrainingArguments = TrainingArguments

    # def _join(self, X_train, y_train):
    #     y_train = DataFrame(y_train, columns=["label"], index=X_train.index)
    #     train_df = X_train.join(y_train)
    #     return train_df

         # @classmethod
        search_space_dict = super().search_space()
        if task in NLG_TASKS:
            search_space_dict["generation_num_beams"] = {
                "domain": tune.randint(2, 5),
                "init_value": 3,
            }
            search_space_dict["generation_max_length"] = {
                "domain": tune.choice([16, 32, 64, 128]),
                "init_value": 64,
            }
        #
        # return search_space_dict

    def _init_hpo_args(self, automl_fit_kwargs: dict = None):
        from .nlp.utils import HPOArgs

        custom_hpo_args = HPOArgs()
        for key, val in automl_fit_kwargs["custom_hpo_args"].items():
            assert (
                key in custom_hpo_args.__dict__
            ), "The specified key {} is not in the argument list of flaml.nlp.utils::HPOArgs".format(
                key
            )
            setattr(custom_hpo_args, key, val)
        self.custom_hpo_args = custom_hpo_args

    def _preprocess(self, X, y=None, task=None, **kwargs):
        from .nlp.utils import tokenize_text

        if X.dtypes[0] == "string":
            return tokenize_text(
                X=X, Y=y, task=task, custom_hpo_args=self.custom_hpo_args
            )
        else:
            return X, None

    def fit(self, X_train: DataFrame, y_train: Series, budget=None, **kwargs):
        from transformers import EarlyStoppingCallback
        from transformers.trainer_utils import set_seed
        from transformers import AutoTokenizer

        import transformers
        from datasets import Dataset
        from .nlp.utils import (
            get_num_labels,
            separate_config,
            load_model,
            compute_checkpoint_freq,
            get_trial_fold_name,
            date_str,
        )

        # TODO: if self._task == QUESTIONANSWERING, uncomment the code below (add indentation before
        #  from .nlp.huggingface.trainer import TrainerForAuto)

        # if self._task in NLG_TASKS:
        #     from .nlp.huggingface.trainer import Seq2SeqTrainerForAuto as TrainerForAuto
        # else:
        from .nlp.huggingface.trainer import TrainerForAuto

        this_params = self.params

        class EarlyStoppingCallbackForAuto(EarlyStoppingCallback):
            def on_train_begin(self, args, state, control, **callback_kwargs):
                self.train_begin_time = time.time()

            def on_step_begin(self, args, state, control, **callback_kwargs):
                self.step_begin_time = time.time()

            def on_step_end(self, args, state, control, **callback_kwargs):
                if state.global_step == 1:
                    self.time_per_iter = time.time() - self.step_begin_time
                if (
                    budget
                    and (
                        time.time() + self.time_per_iter
                        > self.train_begin_time + budget
                    )
                    or state.global_step >= this_params[FineTuningEstimator.ITER_HP]
                ):
                    control.should_training_stop = True
                    control.should_save = True
                    control.should_evaluate = True
                return control

            def on_epoch_end(self, args, state, control, **callback_kwargs):
                if (
                    control.should_training_stop
                    or state.epoch + 1 >= args.num_train_epochs
                ):
                    control.should_save = True
                    control.should_evaluate = True

        set_seed(self.params.get("seed", self._TrainingArguments.seed))

        self._init_hpo_args(kwargs)
        self._metric_name = kwargs["metric"]
        if hasattr(self, "use_ray") is False:
            self.use_ray = kwargs["use_ray"]

        X_val = kwargs.get("X_val")
        y_val = kwargs.get("y_val")

        if self._task not in NLG_TASKS:
            X_train, _ = self._preprocess(X=X_train, task=self._task, **kwargs)
        else:
            X_train, y_train = self._preprocess(
                X=X_train, y=y_train, task=self._task, **kwargs
            )

        train_dataset = Dataset.from_pandas(self._join(X_train, y_train))

        # TODO: set a breakpoint here, observe the resulting train_dataset,
        #  compare it with the output of the tokenized results in your transformer example
        #  for example, if your task is MULTIPLECHOICE, you need to compare train_dataset with
        #  the output of https://github.com/huggingface/transformers/blob/master/examples/pytorch/multiple-choice/run_swag.py#L329
        #  make sure they are the same

        if X_val is not None:
            if self._task not in NLG_TASKS:
                X_val, _ = self._preprocess(X=X_val, task=self._task, **kwargs)
            else:
                X_val, y_val = self._preprocess(
                    X=X_val, y=y_val, task=self._task, **kwargs
                )
            eval_dataset = Dataset.from_pandas(self._join(X_val, y_val))
        else:
            eval_dataset = None

        tokenizer = AutoTokenizer.from_pretrained(
            self.custom_hpo_args.model_path, use_fast=True
        )
        self._tokenizer = tokenizer

        num_labels = get_num_labels(self._task, y_train)

        training_args_config, per_model_config = separate_config(
            self.params, self._task
        )
        ckpt_freq = compute_checkpoint_freq(
            train_data_size=len(X_train),
            custom_hpo_args=self.custom_hpo_args,
            num_train_epochs=training_args_config.get(
                "num_train_epochs", self._TrainingArguments.num_train_epochs
            ),
            batch_size=training_args_config.get(
                "per_device_train_batch_size",
                self._TrainingArguments.per_device_train_batch_size,
            ),
        )

        local_dir = os.path.join(
            self.custom_hpo_args.output_dir, "train_{}".format(date_str())
        )

        if not self.use_ray:
            # if self.params = {}, don't include configuration in trial fold name
            trial_dir = get_trial_fold_name(local_dir, self.params, self.trial_id)
        else:
            import ray

            trial_dir = ray.tune.get_trial_dir()

        if transformers.__version__.startswith("3"):
            training_args = self._TrainingArguments(
                report_to=[],
                output_dir=trial_dir,
                do_train=True,
                do_eval=True,
                eval_steps=ckpt_freq,
                evaluate_during_training=True,
                save_steps=ckpt_freq,
                save_total_limit=0,
                fp16=self.custom_hpo_args.fp16,
                load_best_model_at_end=True,
                **training_args_config,
            )
        else:
            from transformers import IntervalStrategy

            training_args = self._TrainingArguments(
                report_to=[],
                output_dir=trial_dir,
                do_train=True,
                do_eval=True,
                per_device_eval_batch_size=1,
                eval_steps=ckpt_freq,
                evaluation_strategy=IntervalStrategy.STEPS,
                save_steps=ckpt_freq,
                save_total_limit=0,
                fp16=self.custom_hpo_args.fp16,
                load_best_model_at_end=True,
                **training_args_config,
            )

        def _model_init():
            return load_model(
                checkpoint_path=self.custom_hpo_args.model_path,
                task=self._task,
                num_labels=num_labels,
                per_model_config=per_model_config,
            )

        self._model = TrainerForAuto(
            args=training_args,
            model_init=_model_init,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=tokenizer,
            compute_metrics=self._compute_metrics_by_dataset_name,
            callbacks=[EarlyStoppingCallbackForAuto],
        )

        setattr(self._model, "_use_ray", self.use_ray)
        if self._task in NLG_TASKS:
            setattr(self._model, "_is_seq2seq", True)
        self._model.train()

        self.params[self.ITER_HP] = self._model.state.global_step
        self._checkpoint_path = self._select_checkpoint(self._model)

        self._kwargs = kwargs
        self._num_labels = num_labels
        self._per_model_config = per_model_config
        self._training_args_config = training_args_config

        self._ckpt_remains = list(self._model.ckpt_to_metric.keys())

    def _delete_one_ckpt(self, ckpt_location):
        if self.use_ray is False:
            try:
                shutil.rmtree(ckpt_location)
            except FileNotFoundError:
                logger.warning("checkpoint {} not found".format(ckpt_location))

    def cleanup(self):
        super().cleanup()
        if hasattr(self, "_ckpt_remains"):
            for each_ckpt in self._ckpt_remains:
                self._delete_one_ckpt(each_ckpt)

    def _select_checkpoint(self, trainer):
        from transformers.trainer_utils import PREFIX_CHECKPOINT_DIR

        if trainer.ckpt_to_metric:
            best_ckpt, _ = min(
                trainer.ckpt_to_metric.items(), key=lambda x: x[1]["val_loss"]
            )
            best_ckpt_global_step = trainer.ckpt_to_global_step[best_ckpt]
            for each_ckpt in list(trainer.ckpt_to_metric):
                if each_ckpt != best_ckpt:
                    del trainer.ckpt_to_metric[each_ckpt]
                    del trainer.ckpt_to_global_step[each_ckpt]
                    self._delete_one_ckpt(each_ckpt)
        else:
            best_ckpt_global_step = trainer.state.global_step
            best_ckpt = os.path.join(
                trainer.args.output_dir,
                f"{PREFIX_CHECKPOINT_DIR}-{best_ckpt_global_step}",
            )
        self.params[self.ITER_HP] = best_ckpt_global_step
        print(trainer.state.global_step)
        print(trainer.ckpt_to_global_step)
        return best_ckpt

    def _compute_metrics_by_dataset_name(self, eval_pred):
        from .ml import metric_loss_score
        from .nlp.utils import postprocess_text

        predictions, labels = eval_pred

        if self._task in NLG_TASKS:
            if isinstance(predictions, tuple):
                predictions = np.argmax(predictions[0], axis=2)
            decoded_preds = self._tokenizer.batch_decode(
                predictions, skip_special_tokens=True
            )
            labels = np.where(labels != -100, labels, self._tokenizer.pad_token_id)
            decoded_labels = self._tokenizer.batch_decode(
                labels, skip_special_tokens=True
            )
            predictions, labels = postprocess_text(decoded_preds, decoded_labels)
        else:
            predictions = (
                np.squeeze(predictions)
                if self._task == SEQREGRESSION
                else np.argmax(predictions, axis=1)
            )

        return {
            "val_loss": metric_loss_score(
                metric_name=self._metric_name, y_predict=predictions, y_true=labels
            )
        }

    def predict_proba(self, X_test):
        assert (
            self._task in CLASSIFICATION
        ), "predict_proba() only for classification tasks."

        from datasets import Dataset
        from .nlp.huggingface.trainer import TrainerForAuto
        from transformers import TrainingArguments
        from .nlp.utils import load_model

        X_test, _ = self._preprocess(X_test, task=self._task, **self._kwargs)
        test_dataset = Dataset.from_pandas(X_test)

        best_model = load_model(
            checkpoint_path=self._checkpoint_path,
            task=self._task,
            num_labels=self._num_labels,
            per_model_config=self._per_model_config,
        )
        training_args = TrainingArguments(
            per_device_eval_batch_size=1,
            output_dir=self.custom_hpo_args.output_dir,
        )
        self._model = TrainerForAuto(model=best_model, args=training_args)
        predictions = self._model.predict(test_dataset)
        return predictions.predictions

    def predict(self, X_test):
        from datasets import Dataset
        from .nlp.utils import load_model
        from .nlp.huggingface.trainer import TrainerForAuto

        X_test, _ = self._preprocess(X=X_test, task=self._task, **self._kwargs)
        test_dataset = Dataset.from_pandas(X_test)

        best_model = load_model(
            checkpoint_path=self._checkpoint_path,
            task=self._task,
            num_labels=self._num_labels,
            per_model_config=self._per_model_config,
        )
        training_args = self._TrainingArguments(
            per_device_eval_batch_size=1,
            output_dir=self.custom_hpo_args.output_dir,
            **self._training_args_config,
        )
        self._model = TrainerForAuto(model=best_model, args=training_args)
        if self._task not in NLG_TASKS:
            predictions = self._model.predict(test_dataset)
        else:
            predictions = self._model.predict(
                test_dataset,
                max_length=training_args.generation_max_length,
                num_beams=training_args.generation_num_beams,
            )

        if self._task == SEQCLASSIFICATION:
            return np.argmax(predictions.predictions, axis=1)
        elif self._task == SEQREGRESSION:
            return predictions.predictions
        # TODO: elif self._task == your task, return the corresponding prediction
        #  e.g., if your task == QUESTIONANSWERING, you need to return the answer instead
        #  of the index
        elif self._task == SUMMARIZATION:
            if isinstance(predictions.predictions, tuple):
                predictions = np.argmax(predictions.predictions[0], axis=2)
            decoded_preds = self._tokenizer.batch_decode(
                predictions, skip_special_tokens=True
            )
            return decoded_preds

    def config2params(self, config: dict) -> dict:
        params = config.copy()
        params[FineTuningEstimator.ITER_HP] = params.get(
            FineTuningEstimator.ITER_HP, sys.maxsize
        )
        return params

# class DistilBertEstimator(BaseEstimator):
#     """Dstill Bert Estimator.
#     初始化的时候应该输入一个teacher (well-trained), 一个 student.
#     然后对于给定的数据X, Y, 找到最佳的超参数使得此时的student能最好地模仿teacher.
#     """
#
#     name = "DistilBertEstimator"
#
#     def __init__(self, task="seq-classification", student_type='distilbert',teacher_type='bert',**config):
#         super().__init__(task, **config)
#         self.trial_id = str(uuid.uuid1().hex)[:8]
#         print(f"Initialized {self.trial_id}")
#
#         MODEL_CLASSES = {
#             "distilbert": (DistilBertConfig, DistilBertForMaskedLM, DistilBertTokenizer),
#             "roberta": (RobertaConfig, RobertaForMaskedLM, RobertaTokenizer),
#             "bert": (BertConfig, BertForMaskedLM, BertTokenizer),
#             "gpt2": (GPT2Config, GPT2LMHeadModel, GPT2Tokenizer),
#         }
#
#         self.student_type = student_type
#         self.teacher_type = teacher_type
#
#         self._model = None
#         self.student_config_class, self.student_model_class, _ = MODEL_CLASSES[self.student_type]
#         self.teacher_config_class, self.teacher_model_class, self.teacher_tokenizer_class = MODEL_CLASSES[self.teacher_type]
#
#     @classmethod
#     def search_space(cls, **params):
#         return {
#             "learning_rate": {
#                 "domain": tune.loguniform(lower=1e-6, upper=1e-3),
#                 "init_value": 1e-5,
#             },
#             "batch_size": {
#                 "domain": tune.choice([4, 8, 16, 32]),
#                 "init_value": 32,
#             },
#             # "gradient_accumulation_steps": {
#             #     "domain": tune.randint(lower=2, upper=60),
#             #     "init_value": 2,
#             # },
#             "weight_decay": {
#                 "domain": tune.uniform(lower=0.0, upper=0.3),
#                 "init_value": 0.0,
#             },
#             "adam_epsilon": {
#                 "domain": tune.loguniform(lower=1e-8, upper=1e-6),
#                 "init_value": 1e-6,
#             },
#             "seed": {
#               "domain": tune.chioce(list(range(40,45))),
#               "init value": 42
#             },
#             "global_max_steps":{
#                 "domain":sys.maxsize,"init_value":sys.maxsize
#             },
#             "alpha_ce": {
#                 "domain": tune.uniform(lower=0.0, upper=1.0),
#                 "init_value": 0.5,
#             },
#             "alpha_mlm": {
#                 "domain": tune.uniform(lower=0.0, upper=1.0),
#                 "init_value": 0.0,
#             },  # if mlm, use mlm over clm
#             "alpha_clm": {
#                 "domain": tune.uniform(lower=0.0, upper=1.0),
#                 "init_value": 0.5,
#             },
#             "alpha_cos": {
#                 "domain": tune.uniform(lower=0.0, upper=1.0),
#                 "init_value": 0.0,
#             },
#             "alpha_mse": {
#                 "domain": tune.uniform(lower=0.0, upper=1.0),
#                 "init_value": 0.1,
#             },
#         }
#
#
#     def _init_hpo_args(self, automl_fit_kwargs: dict = None):
#         from utils import DISTILHPOArgs
#
#         custom_hpo_args = DISTILHPOArgs()
#         for key, val in automl_fit_kwargs["custom_hpo_args"].items():
#             assert (
#                 key in custom_hpo_args.__dict__
#         ), "The specified key {} is not in the argument list of flaml.nlp.utils::HPOArgs".format(
#             key
#         )
#             setattr(custom_hpo_args, key, val)
#         self.custom_hpo_args = custom_hpo_args
#
#
#     def sanity_checks(self):
#         """
#         A bunch of args sanity checks to perform even starting...
#         """
#         assert (self.custom_hpo_args.mlm and self.params["alpha_mlm"] > 0.0) or (not self.custom_hpo_args.mlm and self.params["alpha_mlm"] == 0.0)
#         assert (self.params["alpha_mlm"] > 0.0 and self.params["alpha_clm"] == 0.0) or (self.params["alpha_mlm"] == 0.0 and self.params["alpha_clm"] > 0.0)
#         if self.custom_hpo_args.mlm:
#             # assert os.path.isfile(args.token_counts)
#             assert (self.student_type in ["roberta", "distilbert"]) and (self.teacher_type in ["roberta", "bert"])
#         else:
#             assert (self.student_type in ["gpt2"]) and (self.teacher_type in ["gpt2"])
#
#         assert self.teacher_type == self.student_type or (
#                 self.student_type == "distilbert" and self.teacher_type == "bert"
#         )
#         # assert os.path.isfile(args.student_config)
#         if self.custom_hpo_args.student_pretrained_weights is not None:
#             assert os.path.isfile(self.custom_hpo_args.student_pretrained_weights)
#
#         if self.custom_hpo_args.freeze_token_type_embds:
#             assert self.student_type in ["roberta"]
#
#         assert self.params["alpha_ce"] >= 0.0
#         assert self.params["alpha_mlm"] >= 0.0
#         assert self.params["alpha_clm"] >= 0.0
#         assert self.params["alpha_mse"] >= 0.0
#         assert self.params["alpha_cos"] >= 0.0
#         assert self.params["alpha_ce"] + self.params["alpha_mlm"] + self.params["alpha_clm"] + self.params["alpha_mse"] + self.params["alpha_cos"] > 0.0
#
#
#     def freeze_pos_embeddings(self,student):
#         if self.student_type == "roberta":
#             student.roberta.embeddings.position_embeddings.weight.requires_grad = False
#         elif self.student_type == "gpt2":
#             student.transformer.wpe.weight.requires_grad = False
#
#
#     def freeze_token_type_embeddings(self,student):
#         if self.student_type == "roberta":
#             student.roberta.embeddings.token_type_embeddings.weight.requires_grad = False
#
#     def fit(self, X_train: DataFrame, y_train: Series, budget=None, **kwargs):
#         import math
#         from torch.optim import AdamW
#         from transformers import get_linear_schedule_with_warmup
#
#         self._init_hpo_args(kwargs)
#         self.sanity_checks()
#
#         # hyperpremeter start
#         learning_rate = self.params["learning_rate"]
#         batch_size = self.params["batch_size"]
#
#
#         gradient_accumulation_steps = self.params["gradient_accumulation_steps"]
#         alpha_ce = self.params["alpha_ce"]
#         alpha_clm = self.params["alpha_clm"]
#         alpha_mlm = self.params["alpha_mlm"]
#         alpha_cos = self.params["alpha_cos"]
#         alpha_mse = self.params["alpha_mse"]
#
#         adam_epsilon = self.params["adam_epsilon"]
#         weight_decay = self.params["weight_decay"]
#         warmup_prop = self.params["warmup_prop"]
#         # hyerpremeter end
#
#
#         # teacher
#         teacher_name = "{}-base-uncased".format(self.teacher_type)
#         teacher = self.teacher_class.from_pretrained(
#             teacher_name, output_hidden_states=True
#         )
#
#         # student
#
#         student_config = "{}-base-uncased.json".format(self.student_type)
#         stu_architecture_config = DistilBertConfig.from_pretrained(student_config)
#         student = self.student_class(stu_architecture_config)
#
#         # freezing #
#         if self.custom_hpo_args.freeze_pos_embs:
#             self.freeze_pos_embeddings(student)
#         if self.custom_hpo_args.freeze_token_type_embds:
#             self.freeze_token_type_embeddings(student)
#
#         # student.train()
#         # teacher.eval()
#
#         assert student.config.vocab_size == teacher.config.vocab_size
#         assert student.config.hidden_size == teacher.config.hidden_size
#         assert (
#             student.config.max_position_embeddings == teacher.config.max_position_embeddings
#         )
#
#         # student_config = student.config
#         # vocab_size = student.config.vocab_size
#
#         # DISTILLER #
#         torch.cuda.empty_cache()
#         distiller = Distiller(
#             params=args, dataset=train_lm_seq_dataset, token_probs=token_probs, student=student, teacher=teacher
#         )
#         distiller.train()
#
#         dataloader = self._preprocess(X_train, y_train, batch_size=batch_size)
#
#         ce_loss_fct = nn.KLDivLoss(reduction="batchmean")
#         lm_loss_fct = nn.CrossEntropyLoss()
#         cosine_loss_fct = nn.CosineEmbeddingLoss(reduction="mean")
#
#         num_steps_epoch = len(dataloader)
#         num_train_optimization_steps = (
#             int(num_steps_epoch / gradient_accumulation_steps * n_epoch) + 1
#         )
#         warmup_steps = math.ceil(num_train_optimization_steps * warmup_prop)
#
#         # # Prepare optimizer and schedule (linear warmup and decay)
#         #
#         # no_decay = ["bias", "LayerNorm.weight"]
#         # optimizer_grouped_parameters = [
#         #     {
#         #         "params": [
#         #             p
#         #             for n, p in student.named_parameters()
#         #             if not any(nd in n for nd in no_decay) and p.requires_grad
#         #         ],
#         #         "weight_decay": weight_decay,
#         #     },
#         #     {
#         #         "params": [
#         #             p
#         #             for n, p in student.named_parameters()
#         #             if any(nd in n for nd in no_decay) and p.requires_grad
#         #         ],
#         #         "weight_decay": 0.0,
#         #     },
#         # ]
#         #
#         # optimizer = AdamW(
#         #     optimizer_grouped_parameters,
#         #     lr=learning_rate,
#         #     eps=adam_epsilon,
#         #     betas=(0.9, 0.98),
#         # )
#         #
#         # scheduler = get_linear_schedule_with_warmup(
#         #     optimizer,
#         #     num_warmup_steps=warmup_steps,
#         #     num_training_steps=num_train_optimization_steps,
#         # )
#
#         # n_total_iter = 0
#         # epoch = 0
#         # total_loss_epochs = []
#         # n_epoch = 3
#         # for _ in range(n_epoch):
#         #     total_loss_epoch = 0
#         #     n_iter = 0
#         #     student.train()
#         #     teacher.eval()
#         #     for batch in tqdm(dataloader):
#         #         student_outputs = student(batch[0], output_hidden_states=True)
#         #         teacher_outputs = teacher(batch[0], output_hidden_states=True)
#         #
#         #         s_logits, s_h = (
#         #             student_outputs["logits"],
#         #             student_outputs["hidden_states"],
#         #         )
#         #         t_logits, t_h = (
#         #             teacher_outputs["logits"],
#         #             teacher_outputs["hidden_states"],
#         #         )
#         #
#         #         assert s_logits.size() == t_logits.size()
#         #
#         #         loss_ce = (
#         #             ce_loss_fct(
#         #                 nn.functional.log_softmax(s_logits / temperature, dim=-1),
#         #                 nn.functional.softmax(t_logits / temperature, dim=-1),
#         #             )
#         #             * (temperature) ** 2
#         #         )
#         #         loss = alpha_ce * loss_ce
#         #
#         #         loss_clm = lm_loss_fct(s_logits, batch[1])
#         #
#         #         loss += alpha_clm * loss_clm
#         #
#         #         dim = s_h[-1].shape[0]
#         #         slh = s_h[-1].view(dim, -1)
#         #         tlh = t_h[-1].view(dim, -1)
#         #         loss_cos = cosine_loss_fct(
#         #             slh, tlh, target=slh.new(slh.size(0)).fill_(1)
#         #         )
#         #         loss += alpha_ca * loss_cos
#         #
#         #         total_loss_epoch += loss.item()
#         #
#         #         # Check for NaN
#         #         if (loss != loss).data.any():
#         #             raise ValueError("NaN detected")
#         #             # sys.exit(1)
#         #
#         #         loss.backward()
#         #         n_iter += 1
#         #         n_total_iter += 1
#         #
#         #         if n_iter % gradient_accumulation_steps == 0:
#         #             optimizer.step()
#         #             optimizer.zero_grad()
#         #             scheduler.step()
#         #
#         #             break
#         #
#         #     total_loss_epochs.append(total_loss_epoch)
#         #     epoch += 1
#         #
#         # self._model = student
#         # self._model.model_id = self.trial_id
#         # return total_loss_epochs[-1]
#
#     def _get_best_student(self):
#         if self._model:
#             print(f"Model id is: {self._model.model_id}")
#             return self._model
#         else:
#             return ValueError("no model")
#
#     def predict_proba(self, X_test):
#
#         y_test_fake = Series(np.zeros(len(X_test)))
#         dataloader = self._preprocess(
#             X_test, y_test_fake, batch_size=min(512, len(X_test) // 10)
#         )
#         best_model = self._get_best_student()  #
#         probas = []
#         for batch in tqdm(dataloader):
#             student_outputs = best_model(batch[0])
#             proba = nn.functional.softmax(student_outputs["logits"], dim=-1)
#             probas.append(proba)
#
#         probas = torch.cat(probas)
#         return probas.data.numpy()
#
#     def predict(self, X_test):
#
#         probas = self.predict_proba(X_test)
#         return np.argmax(probas, axis=1)
#
#     def _preprocess(self, X_train, y_train, batch_size=10):
#
#         dataset = LmSeqsDataset(
#             [np.array(v) for v in X_train["token_ids"].values],
#             y_train,
#             max_model_input_size=50,
#             min_model_input_size=3,
#         )
#
#         dataloader = DataLoader(
#             dataset=dataset,
#             batch_size=batch_size,
#             collate_fn=dataset.batch_sequences,
#         )
#         return dataloader

class SKLearnEstimator(BaseEstimator):
    """The base class for tuning scikit-learn estimators."""

    def __init__(self, task="binary", **config):
        super().__init__(task, **config)

    def _preprocess(self, X):
        if isinstance(X, DataFrame):
            cat_columns = X.select_dtypes(include=["category"]).columns
            if not cat_columns.empty:
                X = X.copy()
                X[cat_columns] = X[cat_columns].apply(lambda x: x.cat.codes)
        elif isinstance(X, np.ndarray) and X.dtype.kind not in "buif":
            # numpy array is not of numeric dtype
            X = DataFrame(X)
            for col in X.columns:
                if isinstance(X[col][0], str):
                    X[col] = X[col].astype("category").cat.codes
            X = X.to_numpy()
        return X


class LGBMEstimator(BaseEstimator):
    """The class for tuning LGBM, using sklearn API."""

    ITER_HP = "n_estimators"
    HAS_CALLBACK = True

    @classmethod
    def search_space(cls, data_size, **params):
        upper = min(32768, int(data_size[0]))
        return {
            "n_estimators": {
                "domain": tune.lograndint(lower=4, upper=upper),
                "init_value": 4,
                "low_cost_init_value": 4,
            },
            "num_leaves": {
                "domain": tune.lograndint(lower=4, upper=upper),
                "init_value": 4,
                "low_cost_init_value": 4,
            },
            "min_child_samples": {
                "domain": tune.lograndint(lower=2, upper=2 ** 7 + 1),
                "init_value": 20,
            },
            "learning_rate": {
                "domain": tune.loguniform(lower=1 / 1024, upper=1.0),
                "init_value": 0.1,
            },
            # 'subsample': {
            #     'domain': tune.uniform(lower=0.1, upper=1.0),
            #     'init_value': 1.0,
            # },
            "log_max_bin": {  # log transformed with base 2
                "domain": tune.lograndint(lower=3, upper=11),
                "init_value": 8,
            },
            "colsample_bytree": {
                "domain": tune.uniform(lower=0.01, upper=1.0),
                "init_value": 1.0,
            },
            "reg_alpha": {
                "domain": tune.loguniform(lower=1 / 1024, upper=1024),
                "init_value": 1 / 1024,
            },
            "reg_lambda": {
                "domain": tune.loguniform(lower=1 / 1024, upper=1024),
                "init_value": 1.0,
            },
        }

    def config2params(self, config: dict) -> dict:
        params = config.copy()
        if "log_max_bin" in params:
            params["max_bin"] = (1 << params.pop("log_max_bin")) - 1
        return params

    @classmethod
    def size(cls, config):
        num_leaves = int(
            round(
                config.get("num_leaves")
                or config.get("max_leaves")
                or 1 << config.get("max_depth", 16)
            )
        )
        n_estimators = int(round(config["n_estimators"]))
        return (num_leaves * 3 + (num_leaves - 1) * 4 + 1.0) * n_estimators * 8

    def __init__(self, task="binary", **config):
        super().__init__(task, **config)
        if "verbose" not in self.params:
            self.params["verbose"] = -1
        if "regression" == task:
            from lightgbm import LGBMRegressor

            self.estimator_class = LGBMRegressor
        elif "rank" == task:
            from lightgbm import LGBMRanker

            self.estimator_class = LGBMRanker
        else:
            from lightgbm import LGBMClassifier

            self.estimator_class = LGBMClassifier
        self._time_per_iter = None
        self._train_size = 0
        self._mem_per_iter = -1
        self.HAS_CALLBACK = self.HAS_CALLBACK and self._callbacks(0, 0) is not None

    def _preprocess(self, X):
        if (
            not isinstance(X, DataFrame)
            and issparse(X)
            and np.issubdtype(X.dtype, np.integer)
        ):
            X = X.astype(float)
        elif isinstance(X, np.ndarray) and X.dtype.kind not in "buif":
            # numpy array is not of numeric dtype
            X = DataFrame(X)
            for col in X.columns:
                if isinstance(X[col][0], str):
                    X[col] = X[col].astype("category").cat.codes
            X = X.to_numpy()
        return X

    def fit(self, X_train, y_train, budget=None, **kwargs):
        start_time = time.time()
        deadline = start_time + budget if budget else np.inf
        n_iter = self.params[self.ITER_HP]
        trained = False
        if not self.HAS_CALLBACK:
            mem0 = psutil.virtual_memory().available if psutil is not None else 1
            if (
                (
                    not self._time_per_iter
                    or abs(self._train_size - X_train.shape[0]) > 4
                )
                and budget is not None
                or self._mem_per_iter < 0
                and psutil is not None
            ) and n_iter > 1:
                self.params[self.ITER_HP] = 1
                self._t1 = self._fit(X_train, y_train, **kwargs)
                if budget is not None and self._t1 >= budget or n_iter == 1:
                    # self.params[self.ITER_HP] = n_iter
                    return self._t1
                mem1 = psutil.virtual_memory().available if psutil is not None else 1
                self._mem1 = mem0 - mem1
                self.params[self.ITER_HP] = min(n_iter, 4)
                self._t2 = self._fit(X_train, y_train, **kwargs)
                mem2 = psutil.virtual_memory().available if psutil is not None else 1
                self._mem2 = max(mem0 - mem2, self._mem1)
                # if self._mem1 <= 0:
                #     self._mem_per_iter = self._mem2 / (self.params[self.ITER_HP] + 1)
                # elif self._mem2 <= 0:
                #     self._mem_per_iter = self._mem1
                # else:
                self._mem_per_iter = min(
                    self._mem1, self._mem2 / self.params[self.ITER_HP]
                )
                # if self._mem_per_iter <= 1 and psutil is not None:
                #     n_iter = self.params[self.ITER_HP]
                self._time_per_iter = (
                    (self._t2 - self._t1) / (self.params[self.ITER_HP] - 1)
                    if self._t2 > self._t1
                    else self._t1
                    if self._t1
                    else 0.001
                )
                self._train_size = X_train.shape[0]
                if (
                    budget is not None
                    and self._t1 + self._t2 >= budget
                    or n_iter == self.params[self.ITER_HP]
                ):
                    # self.params[self.ITER_HP] = n_iter
                    return time.time() - start_time
                trained = True
            # logger.debug(mem0)
            # logger.debug(self._mem_per_iter)
            if n_iter > 1:
                max_iter = min(
                    n_iter,
                    int(
                        (budget - time.time() + start_time - self._t1)
                        / self._time_per_iter
                        + 1
                    )
                    if budget is not None
                    else n_iter,
                    int((1 - FREE_MEM_RATIO) * mem0 / self._mem_per_iter)
                    if psutil is not None and self._mem_per_iter > 0
                    else n_iter,
                )
                if trained and max_iter <= self.params[self.ITER_HP]:
                    return time.time() - start_time
                # when not trained, train at least one iter
                self.params[self.ITER_HP] = max(max_iter, 1)
        if self.HAS_CALLBACK:
            self._fit(
                X_train,
                y_train,
                callbacks=self._callbacks(start_time, deadline),
                **kwargs,
            )
            best_iteration = (
                self._model.get_booster().best_iteration
                if isinstance(self, XGBoostSklearnEstimator)
                else self._model.best_iteration_
            )
            if best_iteration is not None:
                self._model.set_params(n_estimators=best_iteration + 1)
        else:
            self._fit(X_train, y_train, **kwargs)
        train_time = time.time() - start_time
        return train_time

    def _callbacks(self, start_time, deadline) -> List[Callable]:
        return [partial(self._callback, start_time, deadline)]

    def _callback(self, start_time, deadline, env) -> None:
        from lightgbm.callback import EarlyStopException

        now = time.time()
        if env.iteration == 0:
            self._time_per_iter = now - start_time
        if now + self._time_per_iter > deadline:
            raise EarlyStopException(env.iteration, env.evaluation_result_list)
        if psutil is not None:
            mem = psutil.virtual_memory()
            if mem.available / mem.total < FREE_MEM_RATIO:
                raise EarlyStopException(env.iteration, env.evaluation_result_list)


class XGBoostEstimator(SKLearnEstimator):
    """The class for tuning XGBoost regressor, not using sklearn API."""

    @classmethod
    def search_space(cls, data_size, **params):
        upper = min(32768, int(data_size[0]))
        return {
            "n_estimators": {
                "domain": tune.lograndint(lower=4, upper=upper),
                "init_value": 4,
                "low_cost_init_value": 4,
            },
            "max_leaves": {
                "domain": tune.lograndint(lower=4, upper=upper),
                "init_value": 4,
                "low_cost_init_value": 4,
            },
            "max_depth": {
                "domain": tune.choice([0, 6, 12]),
                "init_value": 0,
            },
            "min_child_weight": {
                "domain": tune.loguniform(lower=0.001, upper=128),
                "init_value": 1,
            },
            "learning_rate": {
                "domain": tune.loguniform(lower=1 / 1024, upper=1.0),
                "init_value": 0.1,
            },
            "subsample": {
                "domain": tune.uniform(lower=0.1, upper=1.0),
                "init_value": 1.0,
            },
            "colsample_bylevel": {
                "domain": tune.uniform(lower=0.01, upper=1.0),
                "init_value": 1.0,
            },
            "colsample_bytree": {
                "domain": tune.uniform(lower=0.01, upper=1.0),
                "init_value": 1.0,
            },
            "reg_alpha": {
                "domain": tune.loguniform(lower=1 / 1024, upper=1024),
                "init_value": 1 / 1024,
            },
            "reg_lambda": {
                "domain": tune.loguniform(lower=1 / 1024, upper=1024),
                "init_value": 1.0,
            },
        }

    @classmethod
    def size(cls, config):
        return LGBMEstimator.size(config)

    @classmethod
    def cost_relative2lgbm(cls):
        return 1.6

    def config2params(self, config: dict) -> dict:
        params = config.copy()
        max_depth = params["max_depth"] = params.get("max_depth", 0)
        if max_depth == 0:
            params["grow_policy"] = params.get("grow_policy", "lossguide")
            params["tree_method"] = params.get("tree_method", "hist")
        # params["booster"] = params.get("booster", "gbtree")
        params["use_label_encoder"] = params.get("use_label_encoder", False)
        if "n_jobs" in config:
            params["nthread"] = params.pop("n_jobs")
        return params

    def __init__(
        self,
        task="regression",
        **config,
    ):
        super().__init__(task, **config)
        self.params["verbosity"] = 0

    def fit(self, X_train, y_train, budget=None, **kwargs):
        import xgboost as xgb

        start_time = time.time()
        deadline = start_time + budget if budget else np.inf
        if issparse(X_train):
            self.params["tree_method"] = "auto"
        else:
            X_train = self._preprocess(X_train)
        if "sample_weight" in kwargs:
            dtrain = xgb.DMatrix(X_train, label=y_train, weight=kwargs["sample_weight"])
        else:
            dtrain = xgb.DMatrix(X_train, label=y_train)

        objective = self.params.get("objective")
        if isinstance(objective, str):
            obj = None
        else:
            obj = objective
            if "objective" in self.params:
                del self.params["objective"]
        _n_estimators = self.params.pop("n_estimators")
        callbacks = XGBoostEstimator._callbacks(start_time, deadline)
        if callbacks:
            self._model = xgb.train(
                self.params,
                dtrain,
                _n_estimators,
                obj=obj,
                callbacks=callbacks,
            )
            self.params["n_estimators"] = self._model.best_iteration + 1
        else:
            self._model = xgb.train(self.params, dtrain, _n_estimators, obj=obj)
            self.params["n_estimators"] = _n_estimators
        self.params["objective"] = objective
        del dtrain
        train_time = time.time() - start_time
        return train_time

    def predict(self, X_test):
        import xgboost as xgb

        if not issparse(X_test):
            X_test = self._preprocess(X_test)
        dtest = xgb.DMatrix(X_test)
        return super().predict(dtest)

    @classmethod
    def _callbacks(cls, start_time, deadline):
        try:
            from xgboost.callback import TrainingCallback
        except ImportError:  # for xgboost<1.3
            return None

        class ResourceLimit(TrainingCallback):
            def after_iteration(self, model, epoch, evals_log) -> bool:
                now = time.time()
                if epoch == 0:
                    self._time_per_iter = now - start_time
                if now + self._time_per_iter > deadline:
                    return True
                if psutil is not None:
                    mem = psutil.virtual_memory()
                    if mem.available / mem.total < FREE_MEM_RATIO:
                        return True
                return False

        return [ResourceLimit()]


class XGBoostSklearnEstimator(SKLearnEstimator, LGBMEstimator):
    """The class for tuning XGBoost with unlimited depth, using sklearn API."""

    @classmethod
    def search_space(cls, data_size, **params):
        space = XGBoostEstimator.search_space(data_size)
        space.pop("max_depth")
        return space

    @classmethod
    def cost_relative2lgbm(cls):
        return XGBoostEstimator.cost_relative2lgbm()

    def config2params(self, config: dict) -> dict:
        params = config.copy()
        max_depth = params["max_depth"] = params.get("max_depth", 0)
        if max_depth == 0:
            params["grow_policy"] = params.get("grow_policy", "lossguide")
            params["tree_method"] = params.get("tree_method", "hist")
        params["use_label_encoder"] = params.get("use_label_encoder", False)
        return params

    def __init__(
        self,
        task="binary",
        **config,
    ):
        super().__init__(task, **config)
        del self.params["verbose"]
        self.params["verbosity"] = 0
        import xgboost as xgb

        self.estimator_class = xgb.XGBRegressor
        if "rank" == task:
            self.estimator_class = xgb.XGBRanker
        elif task in CLASSIFICATION:
            self.estimator_class = xgb.XGBClassifier

    def fit(self, X_train, y_train, budget=None, **kwargs):
        if issparse(X_train):
            self.params["tree_method"] = "auto"
        return super().fit(X_train, y_train, budget, **kwargs)

    def _callbacks(self, start_time, deadline) -> List[Callable]:
        return XGBoostEstimator._callbacks(start_time, deadline)


class XGBoostLimitDepthEstimator(XGBoostSklearnEstimator):
    """The class for tuning XGBoost with limited depth, using sklearn API."""

    @classmethod
    def search_space(cls, data_size, **params):
        space = XGBoostEstimator.search_space(data_size)
        space.pop("max_leaves")
        upper = max(6, int(np.log2(data_size[0])))
        space["max_depth"] = {
            "domain": tune.randint(lower=1, upper=min(upper, 16)),
            "init_value": 6,
            "low_cost_init_value": 1,
        }
        space["learning_rate"]["init_value"] = 0.3
        space["n_estimators"]["init_value"] = 10
        return space

    @classmethod
    def cost_relative2lgbm(cls):
        return 64


class RandomForestEstimator(SKLearnEstimator, LGBMEstimator):
    """The class for tuning Random Forest."""

    HAS_CALLBACK = False
    nrows = 101

    @classmethod
    def search_space(cls, data_size, task, **params):
        RandomForestEstimator.nrows = int(data_size[0])
        upper = min(2048, RandomForestEstimator.nrows)
        init = 1 / np.sqrt(data_size[1]) if task in CLASSIFICATION else 1
        lower = min(0.1, init)
        space = {
            "n_estimators": {
                "domain": tune.lograndint(lower=4, upper=upper),
                "init_value": 4,
                "low_cost_init_value": 4,
            },
            "max_features": {
                "domain": tune.loguniform(lower=lower, upper=1.0),
                "init_value": init,
            },
            "max_leaves": {
                "domain": tune.lograndint(
                    lower=4, upper=min(32768, RandomForestEstimator.nrows >> 1)
                ),
                "init_value": 4,
                "low_cost_init_value": 4,
            },
        }
        if task in CLASSIFICATION:
            space["criterion"] = {
                "domain": tune.choice(["gini", "entropy"]),
                # "init_value": "gini",
            }
        return space

    @classmethod
    def cost_relative2lgbm(cls):
        return 2

    def config2params(self, config: dict) -> dict:
        params = config.copy()
        if "max_leaves" in params:
            params["max_leaf_nodes"] = params.get(
                "max_leaf_nodes", params.pop("max_leaves")
            )
        if self._task not in CLASSIFICATION and "criterion" in config:
            params.pop("criterion")
        return params

    def __init__(
        self,
        task="binary",
        **params,
    ):
        super().__init__(task, **params)
        self.params["verbose"] = 0
        self.estimator_class = RandomForestRegressor
        if task in CLASSIFICATION:
            self.estimator_class = RandomForestClassifier


class ExtraTreesEstimator(RandomForestEstimator):
    """The class for tuning Extra Trees."""

    @classmethod
    def cost_relative2lgbm(cls):
        return 1.9

    def __init__(self, task="binary", **params):
        super().__init__(task, **params)
        if "regression" in task:
            self.estimator_class = ExtraTreesRegressor
        else:
            self.estimator_class = ExtraTreesClassifier


class LRL1Classifier(SKLearnEstimator):
    """The class for tuning Logistic Regression with L1 regularization."""

    @classmethod
    def search_space(cls, **params):
        return {
            "C": {
                "domain": tune.loguniform(lower=0.03125, upper=32768.0),
                "init_value": 1.0,
            },
        }

    @classmethod
    def cost_relative2lgbm(cls):
        return 160

    def config2params(self, config: dict) -> dict:
        params = config.copy()
        params["tol"] = params.get("tol", 0.0001)
        params["solver"] = params.get("solver", "saga")
        params["penalty"] = params.get("penalty", "l1")
        return params

    def __init__(self, task="binary", **config):
        super().__init__(task, **config)
        assert task in CLASSIFICATION, "LogisticRegression for classification task only"
        self.estimator_class = LogisticRegression


class LRL2Classifier(SKLearnEstimator):
    """The class for tuning Logistic Regression with L2 regularization."""

    limit_resource = True

    @classmethod
    def search_space(cls, **params):
        return LRL1Classifier.search_space(**params)

    @classmethod
    def cost_relative2lgbm(cls):
        return 25

    def config2params(self, config: dict) -> dict:
        params = config.copy()
        params["tol"] = params.get("tol", 0.0001)
        params["solver"] = params.get("solver", "lbfgs")
        params["penalty"] = params.get("penalty", "l2")
        return params

    def __init__(self, task="binary", **config):
        super().__init__(task, **config)
        assert task in CLASSIFICATION, "LogisticRegression for classification task only"
        self.estimator_class = LogisticRegression


class CatBoostEstimator(BaseEstimator):
    """The class for tuning CatBoost."""

    ITER_HP = "n_estimators"

    @classmethod
    def search_space(cls, data_size, **params):
        upper = max(min(round(1500000 / data_size[0]), 150), 12)
        return {
            "early_stopping_rounds": {
                "domain": tune.lograndint(lower=10, upper=upper),
                "init_value": 10,
                "low_cost_init_value": 10,
            },
            "learning_rate": {
                "domain": tune.loguniform(lower=0.005, upper=0.2),
                "init_value": 0.1,
            },
            "n_estimators": {
                "domain": 8192,
                "init_value": 8192,
            },
        }

    @classmethod
    def size(cls, config):
        n_estimators = config.get("n_estimators", 8192)
        max_leaves = 64
        return (max_leaves * 3 + (max_leaves - 1) * 4 + 1.0) * n_estimators * 8

    @classmethod
    def cost_relative2lgbm(cls):
        return 15

    def _preprocess(self, X):
        if isinstance(X, DataFrame):
            cat_columns = X.select_dtypes(include=["category"]).columns
            if not cat_columns.empty:
                X = X.copy()
                X[cat_columns] = X[cat_columns].apply(
                    lambda x: x.cat.rename_categories(
                        [
                            str(c) if isinstance(c, float) else c
                            for c in x.cat.categories
                        ]
                    )
                )
        elif isinstance(X, np.ndarray) and X.dtype.kind not in "buif":
            # numpy array is not of numeric dtype
            X = DataFrame(X)
            for col in X.columns:
                if isinstance(X[col][0], str):
                    X[col] = X[col].astype("category").cat.codes
            X = X.to_numpy()
        return X

    def config2params(self, config: dict) -> dict:
        params = config.copy()
        params["n_estimators"] = params.get("n_estimators", 8192)
        if "n_jobs" in params:
            params["thread_count"] = params.pop("n_jobs")
        return params

    def __init__(
        self,
        task="binary",
        **config,
    ):
        super().__init__(task, **config)
        self.params.update(
            {
                "verbose": config.get("verbose", False),
                "random_seed": config.get("random_seed", 10242048),
            }
        )
        from catboost import CatBoostRegressor

        self.estimator_class = CatBoostRegressor
        if task in CLASSIFICATION:
            from catboost import CatBoostClassifier

            self.estimator_class = CatBoostClassifier

    def fit(self, X_train, y_train, budget=None, **kwargs):
        start_time = time.time()
        deadline = start_time + budget if budget else np.inf
        train_dir = f"catboost_{str(start_time)}"
        X_train = self._preprocess(X_train)
        if isinstance(X_train, DataFrame):
            cat_features = list(X_train.select_dtypes(include="category").columns)
        else:
            cat_features = []
        n = max(int(len(y_train) * 0.9), len(y_train) - 1000)
        X_tr, y_tr = X_train[:n], y_train[:n]
        if "sample_weight" in kwargs:
            weight = kwargs["sample_weight"]
            if weight is not None:
                kwargs["sample_weight"] = weight[:n]
        else:
            weight = None
        from catboost import Pool, __version__

        model = self.estimator_class(train_dir=train_dir, **self.params)
        if __version__ >= "0.26":
            model.fit(
                X_tr,
                y_tr,
                cat_features=cat_features,
                eval_set=Pool(
                    data=X_train[n:], label=y_train[n:], cat_features=cat_features
                ),
                callbacks=CatBoostEstimator._callbacks(start_time, deadline),
                **kwargs,
            )
        else:
            model.fit(
                X_tr,
                y_tr,
                cat_features=cat_features,
                eval_set=Pool(
                    data=X_train[n:], label=y_train[n:], cat_features=cat_features
                ),
                **kwargs,
            )
        shutil.rmtree(train_dir, ignore_errors=True)
        if weight is not None:
            kwargs["sample_weight"] = weight
        self._model = model
        self.params[self.ITER_HP] = self._model.tree_count_
        train_time = time.time() - start_time
        return train_time

    @classmethod
    def _callbacks(cls, start_time, deadline):
        class ResourceLimit:
            def after_iteration(self, info) -> bool:
                now = time.time()
                if info.iteration == 1:
                    self._time_per_iter = now - start_time
                if now + self._time_per_iter > deadline:
                    return False
                if psutil is not None:
                    mem = psutil.virtual_memory()
                    if mem.available / mem.total < FREE_MEM_RATIO:
                        return False
                return True  # can continue

        return [ResourceLimit()]


class KNeighborsEstimator(BaseEstimator):
    @classmethod
    def search_space(cls, data_size, **params):
        upper = min(512, int(data_size[0] / 2))
        return {
            "n_neighbors": {
                "domain": tune.lograndint(lower=1, upper=upper),
                "init_value": 5,
                "low_cost_init_value": 1,
            },
        }

    @classmethod
    def cost_relative2lgbm(cls):
        return 30

    def config2params(self, config: dict) -> dict:
        params = config.copy()
        params["weights"] = params.get("weights", "distance")
        return params

    def __init__(self, task="binary", **config):
        super().__init__(task, **config)
        if task in CLASSIFICATION:
            from sklearn.neighbors import KNeighborsClassifier

            self.estimator_class = KNeighborsClassifier
        else:
            from sklearn.neighbors import KNeighborsRegressor

            self.estimator_class = KNeighborsRegressor

    def _preprocess(self, X):
        if isinstance(X, DataFrame):
            cat_columns = X.select_dtypes(["category"]).columns
            if X.shape[1] == len(cat_columns):
                raise ValueError("kneighbor requires at least one numeric feature")
            X = X.drop(cat_columns, axis=1)
        elif isinstance(X, np.ndarray) and X.dtype.kind not in "buif":
            # drop categocial columns if any
            X = DataFrame(X)
            cat_columns = []
            for col in X.columns:
                if isinstance(X[col][0], str):
                    cat_columns.append(col)
            X = X.drop(cat_columns, axis=1)
            X = X.to_numpy()
        return X


class Prophet(SKLearnEstimator):
    """The class for tuning Prophet."""

    @classmethod
    def search_space(cls, **params):
        space = {
            "changepoint_prior_scale": {
                "domain": tune.loguniform(lower=0.001, upper=0.05),
                "init_value": 0.05,
                "low_cost_init_value": 0.001,
            },
            "seasonality_prior_scale": {
                "domain": tune.loguniform(lower=0.01, upper=10),
                "init_value": 10,
            },
            "holidays_prior_scale": {
                "domain": tune.loguniform(lower=0.01, upper=10),
                "init_value": 10,
            },
            "seasonality_mode": {
                "domain": tune.choice(["additive", "multiplicative"]),
                "init_value": "multiplicative",
            },
        }
        return space

    def __init__(self, task=TS_FORECAST, n_jobs=1, **params):
        super().__init__(task, **params)

    def _join(self, X_train, y_train):
        assert TS_TIMESTAMP_COL in X_train, (
            "Dataframe for training ts_forecast model must have column"
            f' "{TS_TIMESTAMP_COL}" with the dates in X_train.'
        )
        y_train = DataFrame(y_train, columns=[TS_VALUE_COL])
        train_df = X_train.join(y_train)
        return train_df

    def fit(self, X_train, y_train, budget=None, **kwargs):
        from prophet import Prophet

        current_time = time.time()
        train_df = self._join(X_train, y_train)
        train_df = self._preprocess(train_df)
        cols = list(train_df)
        cols.remove(TS_TIMESTAMP_COL)
        cols.remove(TS_VALUE_COL)
        logging.getLogger("prophet").setLevel(logging.WARNING)
        model = Prophet(**self.params)
        for regressor in cols:
            model.add_regressor(regressor)
        with suppress_stdout_stderr():
            model.fit(train_df)
        train_time = time.time() - current_time
        self._model = model
        return train_time

    def predict(self, X_test):
        if isinstance(X_test, int):
            raise ValueError(
                "predict() with steps is only supported for arima/sarimax."
                " For Prophet, pass a dataframe with the first column containing"
                " the timestamp values."
            )
        if self._model is not None:
            X_test = self._preprocess(X_test)
            forecast = self._model.predict(X_test)
            return forecast["yhat"]
        else:
            logger.warning(
                "Estimator is not fit yet. Please run fit() before predict()."
            )
            return np.ones(X_test.shape[0])


class ARIMA(Prophet):
    """The class for tuning ARIMA."""

    @classmethod
    def search_space(cls, **params):
        space = {
            "p": {
                "domain": tune.quniform(lower=0, upper=10, q=1),
                "init_value": 2,
                "low_cost_init_value": 0,
            },
            "d": {
                "domain": tune.quniform(lower=0, upper=10, q=1),
                "init_value": 2,
                "low_cost_init_value": 0,
            },
            "q": {
                "domain": tune.quniform(lower=0, upper=10, q=1),
                "init_value": 1,
                "low_cost_init_value": 0,
            },
        }
        return space

    def _join(self, X_train, y_train):
        train_df = super()._join(X_train, y_train)
        train_df.index = pd.to_datetime(train_df[TS_TIMESTAMP_COL])
        train_df = train_df.drop(TS_TIMESTAMP_COL, axis=1)
        return train_df

    def fit(self, X_train, y_train, budget=None, **kwargs):
        import warnings

        warnings.filterwarnings("ignore")
        from statsmodels.tsa.arima.model import ARIMA as ARIMA_estimator

        current_time = time.time()
        train_df = self._join(X_train, y_train)
        train_df = self._preprocess(train_df)
        regressors = list(train_df)
        regressors.remove(TS_VALUE_COL)
        if regressors:
            model = ARIMA_estimator(
                train_df[[TS_VALUE_COL]],
                exog=train_df[regressors],
                order=(self.params["p"], self.params["d"], self.params["q"]),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
        else:
            model = ARIMA_estimator(
                train_df,
                order=(self.params["p"], self.params["d"], self.params["q"]),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
        with suppress_stdout_stderr():
            model = model.fit()
        train_time = time.time() - current_time
        self._model = model
        return train_time

    def predict(self, X_test):
        if self._model is not None:
            if isinstance(X_test, int):
                forecast = self._model.forecast(steps=X_test)
            elif isinstance(X_test, DataFrame):
                start = X_test[TS_TIMESTAMP_COL].iloc[0]
                end = X_test[TS_TIMESTAMP_COL].iloc[-1]
                if len(X_test.columns) > 1:
                    X_test = self._preprocess(X_test.drop(columns=TS_TIMESTAMP_COL))
                    regressors = list(X_test)
                    print(start, end, X_test.shape)
                    forecast = self._model.predict(
                        start=start, end=end, exog=X_test[regressors]
                    )
                else:
                    forecast = self._model.predict(start=start, end=end)
            else:
                raise ValueError(
                    "X_test needs to be either a pandas Dataframe with dates as the first column"
                    " or an int number of periods for predict()."
                )
            return forecast
        else:
            return np.ones(X_test if isinstance(X_test, int) else X_test.shape[0])


class SARIMAX(ARIMA):
    """The class for tuning SARIMA."""

    @classmethod
    def search_space(cls, **params):
        space = {
            "p": {
                "domain": tune.quniform(lower=0, upper=10, q=1),
                "init_value": 2,
                "low_cost_init_value": 0,
            },
            "d": {
                "domain": tune.quniform(lower=0, upper=10, q=1),
                "init_value": 2,
                "low_cost_init_value": 0,
            },
            "q": {
                "domain": tune.quniform(lower=0, upper=10, q=1),
                "init_value": 1,
                "low_cost_init_value": 0,
            },
            "P": {
                "domain": tune.quniform(lower=0, upper=10, q=1),
                "init_value": 1,
                "low_cost_init_value": 0,
            },
            "D": {
                "domain": tune.quniform(lower=0, upper=10, q=1),
                "init_value": 1,
                "low_cost_init_value": 0,
            },
            "Q": {
                "domain": tune.quniform(lower=0, upper=10, q=1),
                "init_value": 1,
                "low_cost_init_value": 0,
            },
            "s": {
                "domain": tune.choice([1, 4, 6, 12]),
                "init_value": 12,
            },
        }
        return space

    def fit(self, X_train, y_train, budget=None, **kwargs):
        import warnings

        warnings.filterwarnings("ignore")
        from statsmodels.tsa.statespace.sarimax import SARIMAX as SARIMAX_estimator

        current_time = time.time()
        train_df = self._join(X_train, y_train)
        train_df = self._preprocess(train_df)
        regressors = list(train_df)
        regressors.remove(TS_VALUE_COL)
        if regressors:
            model = SARIMAX_estimator(
                train_df[[TS_VALUE_COL]],
                exog=train_df[regressors],
                order=(self.params["p"], self.params["d"], self.params["q"]),
                seasonality_order=(
                    self.params["P"],
                    self.params["D"],
                    self.params["Q"],
                    self.params["s"],
                ),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
        else:
            model = SARIMAX_estimator(
                train_df,
                order=(self.params["p"], self.params["d"], self.params["q"]),
                seasonality_order=(
                    self.params["P"],
                    self.params["D"],
                    self.params["Q"],
                    self.params["s"],
                ),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
        with suppress_stdout_stderr():
            model = model.fit()
        train_time = time.time() - current_time
        self._model = model
        return train_time


class suppress_stdout_stderr(object):
    def __init__(self):
        # Open a pair of null files
        self.null_fds = [os.open(os.devnull, os.O_RDWR) for x in range(2)]
        # Save the actual stdout (1) and stderr (2) file descriptors.
        self.save_fds = (os.dup(1), os.dup(2))

    def __enter__(self):
        # Assign the null pointers to stdout and stderr.
        os.dup2(self.null_fds[0], 1)
        os.dup2(self.null_fds[1], 2)

    def __exit__(self, *_):
        # Re-assign the real stdout/stderr back to (1) and (2)
        os.dup2(self.save_fds[0], 1)
        os.dup2(self.save_fds[1], 2)
        # Close the null files
        os.close(self.null_fds[0])
        os.close(self.null_fds[1])

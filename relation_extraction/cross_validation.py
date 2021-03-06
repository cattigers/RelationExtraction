import os
import shutil
import numpy as np
import itertools
import load_data
import time

from machine_learning_models import tf_feed_forward as nn


def parallel_k_fold_cross_validation(batch_id, k, pmids, candidate_sentences, distant_interactions, reverse_distant_interactions, hidden_array, key_order):

    pmids = list(pmids)
    #split training sentences for cross validation
    ten_fold_length = len(pmids)/k
    all_chunks = [pmids[i:i + ten_fold_length] for i in xrange(0, len(pmids), ten_fold_length)]

    #total_test = [] #test_labels for instances
    #total_predicted_prob = [] #test_probability returns for instances
    #total_instances = []


    fold_chunks = all_chunks[:]
    fold_test_abstracts = set(fold_chunks.pop(batch_id))
    fold_training_abstracts = set(list(itertools.chain.from_iterable(fold_chunks)))

    fold_training_sentences = []
    fold_test_sentences = []

    for candidate_sentence in candidate_sentences:
        if candidate_sentence.pmid in fold_test_abstracts:
            fold_test_sentences.append(candidate_sentence)
        else:
            fold_training_sentences.append(candidate_sentence)


    fold_training_instances, \
    fold_dep_dictionary, \
    fold_dep_word_dictionary, \
    fold_dep_element_dictionary, \
    fold_between_word_dictionary = load_data.build_instances_training(fold_training_sentences,
                                                                      distant_interactions,
                                                                      reverse_distant_interactions,
                                                                      key_order)


    #train model
    X = []
    y = []
    for t in fold_training_instances:
        X.append(t.features)
        y.append(t.label)


    fold_train_X = np.array(X)
    fold_train_y = np.array(y)


    model_dir = './model_building_meta_data/test' +str(batch_id) + str(time.time()).replace('.','')
    if os.path.exists(model_dir):
        shutil.rmtree(model_dir)

    fold_test_instances = load_data.build_instances_testing(fold_test_sentences,
                                                            fold_dep_dictionary, fold_dep_word_dictionary,
                                                            fold_dep_element_dictionary,
                                                            fold_between_word_dictionary,
                                                            distant_interactions, reverse_distant_interactions,
                                                            key_order)

    # group instances by pmid and build feature array
    fold_test_features = []
    fold_test_labels = []
    pmid_test_instances = {}
    for test_index in range(len(fold_test_instances)):
        fti = fold_test_instances[test_index]
        if fti.sentence.pmid not in pmid_test_instances:
            pmid_test_instances[fti.sentence.pmid] = []
        pmid_test_instances[fti.sentence.pmid].append(test_index)
        fold_test_features.append(fti.features)
        fold_test_labels.append(fti.label)

    fold_test_X = np.array(fold_test_features)
    fold_test_y = np.array(fold_test_labels)


    test_model = nn.feed_forward_train(fold_train_X,
                                       fold_train_y,
                                       fold_test_X,
                                       fold_test_y,
                                       hidden_array,
                                       model_dir + '/', key_order)


    fold_test_predicted_prob = nn.neural_network_test_tfrecord(fold_test_X, fold_test_y, test_model)

    #instance level grouping
    total_predicted_prob = fold_test_predicted_prob.tolist()
    total_test = fold_test_y.tolist()
    total_instances = fold_test_instances

    total_test = np.array(total_test)
    total_predicted_prob = np.array(total_predicted_prob)



    return total_predicted_prob, total_instances

import os
import sys
import collections
import itertools
import cPickle as pickle

import math
import random
import numpy as np

import tensorflow as tf



from lxml import etree

from structures.sentence_structure import Sentence, Token, Dependency
from structures.instances import Instance
from machine_learning_models import tf_lstm as lstm


def np_to_tfrecord(features,labels,tfresult_file):
    """
    converts np aray totfrecord
    :param features: np array of features
    :param labels: np array of labels
    :param tfresult_file: name of tfrecord file
    :return:  tfrecord file path
    """
    writer = tf.python_io.TFRecordWriter(tfresult_file)
    #print(features.shape[0])
    for i in range(features.shape[0]):
        x = features[i]
        x= np.array(x,dtype='int8')
        x=x.tobytes()
        #print(x.shape)
        y = labels[i]
        y = np.array(y,dtype='int8')
        y = y.tobytes()

        feature_dict = {}
        feature_dict['x'] = tf.train.Feature(bytes_list=tf.train.BytesList(value=[x]))
        feature_dict['y'] = tf.train.Feature(bytes_list=tf.train.BytesList(value=[y]))
        example = tf.train.Example(features=tf.train.Features(feature=feature_dict))
        serialized=example.SerializeToString()
        #print(serialized)
        writer.write(serialized)
    writer.close()

    return tfresult_file

def np_to_lstm_tfrecord(dep_path_list_features,dep_word_features,dep_type_path_length,
                                                         dep_word_path_length,labels,tfresult_file):
    """

    :param dep_path_list_features: dependency path type features
    :param dep_word_features:  dependency word path features
    :param dep_type_path_length:  dep type path length
    :param dep_word_path_length: dep word path length
    :param labels: distantly trained labels
    :param tfresult_file: tfrecord file path
    :return: tfrecord file path
    """
    writer = tf.python_io.TFRecordWriter(tfresult_file)
    #print(features.shape[0])
    for i in range(len(labels)):
        dep_path_list_feat = dep_path_list_features[i]
        dep_path_list_feat = np.array(dep_path_list_feat,dtype='int32')
        dep_path_list_feat=dep_path_list_feat.tobytes()

        dep_word_feat = dep_word_features[i]
        dep_word_feat = np.array(dep_word_feat, dtype='int32')
        dep_word_feat = dep_word_feat.tobytes()

        dep_path_length = dep_type_path_length[i]
        dep_path_length = np.array(dep_path_length,dtype='int32')
        dep_path_length = dep_path_length.tobytes()
        #print(dep_path_length)

        dep_word_length = dep_word_path_length[i]
        dep_word_length = np.array(dep_word_length,dtype='int32')
        dep_word_length = dep_word_length.tobytes()

        y = labels[i]
        y = np.array(y,dtype='int32')
        y = y.tobytes()

        feature_dict = {}
        feature_dict['dep_path_list'] = tf.train.Feature(bytes_list=tf.train.BytesList(value=[dep_path_list_feat]))
        feature_dict['dep_word_feat'] = tf.train.Feature(bytes_list=tf.train.BytesList(value=[dep_word_feat]))
        feature_dict['dep_path_length'] = tf.train.Feature(bytes_list=tf.train.BytesList(value=[dep_path_length]))
        feature_dict['dep_word_length'] = tf.train.Feature(bytes_list=tf.train.BytesList(value=[dep_word_length]))
        feature_dict['y'] = tf.train.Feature(bytes_list=tf.train.BytesList(value=[y]))
        #print(feature_dict['x'])


        example = tf.train.Example(features=tf.train.Features(feature=feature_dict))
        serialized=example.SerializeToString()
        #print(serialized)
        writer.write(serialized)
    writer.close()

    return tfresult_file


def build_dataset(words, occur_count = None):
    """
    builds data dictionaries for list of word appearances
    :param words: list of words
    :param occur_count: number of words to filter
    :return: return data dictionary, count dictionary, word to index dictionary, index to word dictionary
    """

    num_total_words = len(set(words))
    discard_count = 0
    if occur_count is not None:
        word_count_dict = collections.Counter(words)
        discard_count = sum(1 for i in word_count_dict.values() if i < occur_count)
    num_words = num_total_words - discard_count
    count = []
    count.extend(collections.Counter(words).most_common(num_words))
    dictionary = dict()
    for word, _ in count:
        dictionary[word] = len(dictionary)
    data = list()
    for word in words:
        if word in dictionary:
            index = dictionary[word]
            data.append(index)
    reversed_dictionary = dict(zip(dictionary.values(), dictionary.keys()))
    return data, count, dictionary, reversed_dictionary

def feature_pruning(feature_dict,feature_count_tuples,prune_val):
    """
    Feature pruning if not done earlier - Don't really need this  function
    :param feature_dict: input dictionary
    :param feature_count_tuples: counts of dictionary
    :param prune_val: value to filter out
    :return: feature dict
    """
    feature_count_dict = dict(feature_count_tuples)
    for key, value in feature_count_dict.iteritems():
        if value < prune_val:
            popped_element = feature_dict.pop(key)

    return feature_dict

def build_instances_training(candidate_sentences, distant_interactions,reverse_distant_interactions,key_order, supplemental_dict):
    """
    Builds instances for training
    :param candidate_sentences: sentences
    :param distant_interactions:
    :param reverse_distant_interactions:
    :param key_order:
    :param entity_1_list:
    :param entity_2_list:
    :return:
    """
    # initialize vocabularies for different features
    stop_list = get_stop_list(os.path.dirname(os.path.realpath(__file__)) + '/static_data/stop_list.txt')

    path_word_vocabulary = []
    words_between_entities_vocabulary = []
    dep_type_vocabulary = []
    dep_type_word_elements_vocabulary = []
    candidate_instances = []
    for candidate_sentence in candidate_sentences:
        entity_pairs = candidate_sentence.get_entity_pairs()

        for pair in entity_pairs:
            entity_1_token = candidate_sentence.get_token(pair[0][0])
            entity_2_token = candidate_sentence.get_token(pair[1][0])
            entity_1 = set(entity_1_token.get_normalized_ner().split('|'))
            entity_2 = set(entity_2_token.get_normalized_ner().split('|'))


            if len(entity_1.intersection(stop_list)) > 0 or len(entity_2.intersection(stop_list)) > 0:
                continue

            gene_to_gene = False
            if 'GENE' in entity_1_token.get_ner() and 'GENE' in entity_2_token.get_ner():
                gene_to_gene = True

            entity_combos = set(itertools.product(entity_1,entity_2))

            forward_train_instance = Instance(candidate_sentence, pair[0], pair[1], [0]*len(key_order))
            reverse_train_instance = Instance(candidate_sentence, pair[1], pair[0], [0]*len(key_order))

            for i in range(len(key_order)):
                distant_key = key_order[i]
                if 'SYMMETRIC' in distant_key:
                    if len(entity_combos.intersection(distant_interactions[distant_key]))>0 or len(entity_combos.intersection(reverse_distant_interactions[distant_key]))>0:
                        forward_train_instance.set_label_i(1,i)
                        reverse_train_instance.set_label_i(1,i)
                else:
                    if len(entity_combos.intersection(distant_interactions[distant_key])) > 0:
                        forward_train_instance.set_label_i(1, i)
                    elif len(entity_combos.intersection(reverse_distant_interactions[distant_key]))>0:
                        reverse_train_instance.set_label_i(1, i)

            path_word_vocabulary += forward_train_instance.dependency_words
            path_word_vocabulary += reverse_train_instance.dependency_words
            words_between_entities_vocabulary += forward_train_instance.between_words
            words_between_entities_vocabulary += reverse_train_instance.between_words
            dep_type_word_elements_vocabulary += forward_train_instance.dependency_elements
            dep_type_word_elements_vocabulary += reverse_train_instance.dependency_elements
            dep_type_vocabulary.append(forward_train_instance.dependency_path_string)
            dep_type_vocabulary.append(reverse_train_instance.dependency_path_string)

            candidate_instances.append(forward_train_instance)
            if gene_to_gene is True:
                candidate_instances.append(reverse_train_instance)


    data, count, dep_path_word_dictionary, reversed_dictionary = build_dataset(path_word_vocabulary,100)
    dep_data, dep_count, dep_dictionary, dep_reversed_dictionary = build_dataset(dep_type_vocabulary,100)
    dep_element_data, dep_element_count, dep_element_dictionary, dep_element_reversed_dictionary = build_dataset(
        dep_type_word_elements_vocabulary,100)
    between_data, between_count, between_word_dictionary, between_reversed_dictionary = build_dataset(
        words_between_entities_vocabulary,100)

    print(dep_dictionary)
    print(dep_path_word_dictionary)
    print(between_word_dictionary)
    print(dep_element_dictionary)

    for ci in candidate_instances:
        ci.build_features(dep_dictionary, dep_path_word_dictionary, dep_element_dictionary, between_word_dictionary)

    return candidate_instances, dep_dictionary, dep_path_word_dictionary, dep_element_dictionary, between_word_dictionary

def build_instances_testing(test_sentences, dep_dictionary, dep_path_word_dictionary, dep_element_dictionary, between_word_dictionary,
                            distant_interactions,reverse_distant_interactions, key_order,supplemental_dict ,dep_path_type_dictionary=None):
    """
    Builds instances for testing
    :param test_sentences:
    :param dep_dictionary:
    :param dep_path_word_dictionary:
    :param dep_element_dictionary:
    :param between_word_dictionary:
    :param distant_interactions:
    :param reverse_distant_interactions:
    :param key_order:
    :param entity_1_list:  default is None
    :param entity_2_list: default is None
    :param dep_path_type_dictionary: default is None if not, that means we're creating LSTM model instances
    :return: assembled test instances
    """
    test_instances = []
    stop_list = get_stop_list(os.path.dirname(os.path.realpath(__file__)) + '/static_data/stop_list.txt')
    for test_sentence in test_sentences:
        entity_pairs = test_sentence.get_entity_pairs()

        for pair in entity_pairs:
            entity_1_token = test_sentence.get_token(pair[0][0])
            entity_2_token = test_sentence.get_token(pair[1][0])
            entity_1 = set(entity_1_token.get_normalized_ner().split('|'))
            entity_2 = set(entity_2_token.get_normalized_ner().split('|'))


            if len(entity_1.intersection(stop_list)) > 0 or len(entity_2.intersection(stop_list)) > 0:
                continue

            gene_to_gene = False
            if 'GENE' in entity_1_token.get_ner() and 'GENE' in entity_2_token.get_ner():
                gene_to_gene = True



            entity_combos = set(itertools.product(entity_1,entity_2))
            forward_test_instance = Instance(test_sentence, pair[0], pair[1], [0] *len(key_order))
            reverse_test_instance = Instance(test_sentence, pair[1], pair[0], [0] *len(key_order))


            for i in range(len(key_order)):
                distant_key = key_order[i]
                if 'SYMMETRIC' in distant_key:
                    if len(entity_combos.intersection(distant_interactions[distant_key]))>0 or len(entity_combos.intersection(reverse_distant_interactions[distant_key]))>0:
                        forward_test_instance.set_label_i(1,i)
                        reverse_test_instance.set_label_i(1,i)

                else:
                    if len(entity_combos.intersection(distant_interactions[distant_key])) > 0:
                        forward_test_instance.set_label_i(1, i)
                    elif len(entity_combos.intersection(reverse_distant_interactions[distant_key]))>0:
                        reverse_test_instance.set_label_i(1, i)

            test_instances.append(forward_test_instance)
            if gene_to_gene is True:
                test_instances.append(reverse_test_instance)

    if dep_path_type_dictionary is None:
        for instance in test_instances:
            instance.build_features(dep_dictionary, dep_path_word_dictionary, dep_element_dictionary,  between_word_dictionary)
    else:
        for instance in test_instances:
            instance.build_lstm_features(dep_path_type_dictionary,dep_path_word_dictionary)


    return test_instances

def build_instances_predict(predict_sentences,dep_dictionary, dep_word_dictionary, dep_element_dictionary, between_word_dictionary,key_order,dep_path_type_dictionary=None):
    """
    buld instances for predicting values
    :param predict_sentences:
    :param dep_dictionary:
    :param dep_word_dictionary:
    :param dep_element_dictionary:
    :param between_word_dictionary:
    :param key_order:
    :param entity_1_list:
    :param entity_2_list:
    :param dep_path_type_dictionary:
    :return: prediciton instances
    """
    predict_instances = []
    stop_list = get_stop_list(os.path.dirname(os.path.realpath(__file__)) + '/static_data/stop_list.txt')
    for p_sentence in predict_sentences:

        entity_pairs = p_sentence.get_entity_pairs()

        for pair in entity_pairs:
            entity_1_token = p_sentence.get_token(pair[0][0])
            entity_2_token = p_sentence.get_token(pair[1][0])
            entity_1 = set(entity_1_token.get_normalized_ner().split('|'))
            entity_2 = set(entity_2_token.get_normalized_ner().split('|'))

            if len(entity_1.intersection(stop_list)) > 0 or len(entity_2.intersection(stop_list)) > 0:
                continue

            gene_to_gene = False
            if 'GENE' in entity_1_token.get_ner() and 'GENE' in entity_2_token.get_ner():
                gene_to_gene = True


            forward_predict_instance = Instance(p_sentence, pair[0], pair[1], [-1]*len(key_order))
            if gene_to_gene is True:
                reverse_predict_instance = Instance(p_sentence, pair[1], pair[0], [-1]*len(key_order))

            predict_instances.append(forward_predict_instance)

    if dep_path_type_dictionary is None:
        for instance in predict_instances:
            instance.build_features(dep_dictionary, dep_word_dictionary, dep_element_dictionary, between_word_dictionary)

    else:
        for instance in predict_instances:
            instance.build_lstm_features(dep_path_type_dictionary,dep_word_dictionary)

    return predict_instances

def load_xml(xml_file, entity_1, entity_2):
    """
    load xml files
    :param xml_file:
    :param entity_1:
    :param entity_2:
    :return:
    """
    tree = etree.parse(xml_file)
    root = tree.getroot()
    candidate_sentences = []
    sentences = list(root.iter('sentence'))
    pmids = set()

    for sentence in sentences:
        candidate_sentence = Sentence(sentence.find('PMID').text,sentence.get('id')) #get candidate sentence find for pmid because its a tag, get for 'id' because its an attribute
        tokens = list(sentence.iter('token')) #get tokens for sentence

        for token in tokens:
            normalized_ner = None
            ner = token.find('NER').text
            if token.find('NormalizedNER') is not None:
                normalized_ner = token.find('NormalizedNER').text
            #create token objects for sentences. Use to get word, lemma, POS, etc.
            candidate_token = Token(token.get('id'), token.find('word').text, token.find('lemma').text, token.find('CharacterOffsetBegin').text,
                                    token.find('CharacterOffsetEnd').text, token.find('POS').text, ner, normalized_ner)
            candidate_sentence.add_token(candidate_token)
        #gets dependencies between tokens from stanford dependency parse
        dependencies = list(sentence.iter('dependencies'))
        basic_dependencies = dependencies[0]
        #list of all dependencies in sentence
        deps = list(basic_dependencies.iter('dep'))
        #generates list of all dependencies within a sentence
        for d in deps:
            candidate_dep = Dependency(d.get('type'), candidate_sentence.get_token(d.find('governor').get('idx')), candidate_sentence.get_token(d.find('dependent').get('idx')))
            candidate_sentence.add_dependency(candidate_dep)
        # generates dependency matrix
        candidate_sentence.build_dependency_matrix()
        #gets entity pairs of sentence
        candidate_sentence.generate_entity_pairs(entity_1, entity_2)
        if candidate_sentence.get_entity_pairs() is not None:
            candidate_sentences.append(candidate_sentence)
            pmids.add(candidate_sentence.pmid)

    return candidate_sentences, pmids


def load_distant_kb(distant_kb_file, column_a, column_b,distant_rel_col,supplemental_dict):
    """
    loads data from knowldege bases into tuples
    :param distant_kb_file:
    :param column_a:
    :param column_b:
    :param distant_rel_col:
    :return:
    """
    distant_interactions = set()
    reverse_distant_interactions = set()
    #reads in lines from kb file
    file = open(distant_kb_file,'rU')
    lines = file.readlines()
    file.close()
    for l in lines:
        split_line = l.split('\t')
        #column_a is entity_1 column_b is entity 2
        entity_a = split_line[column_a]
        entity_b = split_line[column_b]
        if entity_a in supplemental_dict:
            entity_a = set([entity_a]).union(supplemental_dict[entity_a])
        else:
            entity_a = set([entity_a])
        if entity_b in supplemental_dict:
            entity_b = set([entity_b]).union(supplemental_dict[entity_b])
        else:
            entity_b = set([entity_b])
        for tuple in set(itertools.product(entity_a,entity_b)):
            if split_line[distant_rel_col].endswith('by') is False:
                distant_interactions.add(tuple)
            else:
                reverse_distant_interactions.add(tuple)

    #returns both forward and backward tuples for relations
    return distant_interactions,reverse_distant_interactions

def load_id_list(id_list,column_a):
    """
    loads normalized ids for entities, only called if file given
    :param id_list:
    :param column_a:
    :return:
    """

    id_set = set()
    file = open(id_list,'rU')
    lines = file.readlines()
    file.close()

    for l in lines:
        split_line = l.split('\t')
        id_set.add(split_line[column_a])

    return id_set



def load_abstracts_from_directory(directory_folder,entity_1,entity_2):
    print(directory_folder)
    total_abstract_sentences = []
    total_pmids = set()
    for path, subdirs, files in os.walk(directory_folder):
        for name in files:
            if name.endswith('.txt'):
                print(name)
                xmlpath = os.path.join(path, name)
                abstract_sentences,pmids = load_xml(xmlpath,entity_1,entity_2)
                if len(abstract_sentences) > 0:
                    total_abstract_sentences += abstract_sentences
                    total_pmids = total_pmids.union(pmids)

            else:
                continue


    return total_pmids,total_abstract_sentences

def load_abstracts_from_pickle(pickle_file):
    """
    load asbtracts from pickle, don't know what this is for
    :param pickle_file:
    :return:
    """
    abstract_dict = pickle.load( open(pickle_file, "rb" ) )
    return abstract_dict


def load_distant_directories(directional_distant_directory,symmetric_distant_directory,distant_entity_a_col,
                             distant_entity_b_col,distant_rel_col,supplemental_dict):
    """
    load distant directories
    :param directional_distant_directory:
    :param symmetric_distant_directory:
    :param distant_entity_a_col:
    :param distant_entity_b_col:
    :param distant_rel_col:
    :return: forward and reverse dictionaries for each type
    """
    forward_dictionary = {}
    reverse_dictionary = {}
    for filename in os.listdir(directional_distant_directory):
        if filename.endswith('.txt') is False:
            continue
        distant_interactions,reverse_distant_interactions = load_distant_kb(directional_distant_directory+'/'+filename,
                                                                            distant_entity_a_col,distant_entity_b_col,distant_rel_col,supplemental_dict)
        forward_dictionary[filename] = distant_interactions
        reverse_dictionary[filename] = reverse_distant_interactions

    for filename in os.listdir(symmetric_distant_directory):
        if filename.endswith('.txt') is False:
            continue
        distant_interactions,reverse_distant_interactions = load_distant_kb(symmetric_distant_directory+'/'+filename,
                                                                            distant_entity_a_col,distant_entity_b_col,distant_rel_col,supplemental_dict)
        forward_dictionary['SYMMETRIC'+filename] = distant_interactions
        reverse_dictionary['SYMMETRIC'+filename] = reverse_distant_interactions

    return forward_dictionary, reverse_dictionary


def build_dictionaries_from_directory(directory_folder,entity_a,entity_b, entity_1_list=None,entity_2_list=None,LSTM=False):
    """
    build feature dictionaries from directory of abstracts
    :param directory_folder:
    :param entity_a:
    :param entity_b:
    :param entity_1_list:
    :param entity_2_list:
    :param LSTM:
    :return:
    """
    print(directory_folder)
    path_word_vocabulary = []
    words_between_entities_vocabulary = []
    dep_type_vocabulary = []
    dep_type_word_elements_vocabulary = []
    dep_type_list_vocabulary = []

    total_pmids = set()
    for path, subdirs, files in os.walk(directory_folder):
        for name in files:
            if name.endswith('.txt'):
                print(name)
                xmlpath = os.path.join(path, name)
                abstract_sentences, pmids = load_xml(xmlpath, entity_a, entity_b)
                for candidate_sentence in abstract_sentences:
                    entity_pairs = candidate_sentence.get_entity_pairs()

                    for pair in entity_pairs:
                        entity_1_token = candidate_sentence.get_token(pair[0][0])
                        entity_2_token = candidate_sentence.get_token(pair[1][0])
                        entity_1 = entity_1_token.get_normalized_ner().split('|')
                        entity_2 = entity_2_token.get_normalized_ner().split('|')

                        if entity_1_list is not None:
                            if len(set(entity_1).intersection(entity_1_list)) == 0:
                                continue

                            # check if entity_2 overlaps with entity_1_list if so continue
                            if len(set(entity_2).intersection(entity_1_list)) > 0:
                                continue

                        if entity_2_list is not None:
                            if len(set(entity_2).intersection(entity_2_list)) == 0:
                                continue

                            # check if entity_1 overlaps with entity_2_list if so continue
                            if len(set(entity_1).intersection(entity_2_list)) > 0:
                                continue

                        entity_combos = set(itertools.product(entity_1, entity_2))
                        # print(entity_combos)

                        forward_train_instance = Instance(candidate_sentence, pair[0], pair[1], None)
                        # print(forward_train_instance.dependency_elements)
                        reverse_train_instance = Instance(candidate_sentence, pair[1], pair[0], None)

                        #get vocabs
                        path_word_vocabulary += forward_train_instance.dependency_words
                        path_word_vocabulary += reverse_train_instance.dependency_words
                        words_between_entities_vocabulary += forward_train_instance.between_words
                        words_between_entities_vocabulary += reverse_train_instance.between_words
                        dep_type_word_elements_vocabulary += forward_train_instance.dependency_elements
                        dep_type_word_elements_vocabulary += reverse_train_instance.dependency_elements
                        dep_type_list_vocabulary += forward_train_instance.dependency_path_list
                        dep_type_list_vocabulary += reverse_train_instance.dependency_path_list
                        dep_type_vocabulary.append(forward_train_instance.dependency_path_string)
                        dep_type_vocabulary.append(reverse_train_instance.dependency_path_string)


            else:
                continue

    data, count, dep_path_word_dictionary, reversed_dictionary = build_dataset(path_word_vocabulary,100)
    dep_data, dep_count, dep_dictionary, dep_reversed_dictionary = build_dataset(dep_type_vocabulary,100)
    dep_element_data, dep_element_count, dep_element_dictionary, dep_element_reversed_dictionary = build_dataset(
        dep_type_word_elements_vocabulary,100)
    between_data, between_count, between_word_dictionary, between_reversed_dictionary = build_dataset(
        words_between_entities_vocabulary,100)
    dep_type_list_data, dep_type_list_count, dep_type_list_dictionary, dep_type_list_reversed_dictionary = build_dataset(
        dep_type_list_vocabulary, 0)


    if LSTM is False:
        return dep_dictionary, dep_path_word_dictionary, dep_element_dictionary, between_word_dictionary
    else:
        unk_pad_dep = len(dep_type_list_dictionary)
        unk_pad_word = len(dep_path_word_dictionary)
        dep_type_list_dictionary['UNKNOWN_WORD'] = unk_pad_dep
        dep_path_word_dictionary['UNKNOWN_WORD'] = unk_pad_word
        dep_type_list_dictionary['PADDING_WORD'] = unk_pad_dep + 1
        dep_path_word_dictionary['PADDING_WORD'] = unk_pad_word + 1
        word2vec_embeddings = None
        if os.path.exists(os.path.dirname(os.path.realpath(__file__)) +'/machine_learning_models/PubMed-w2v.bin'):
            print('embeddings exist')
            word2vec_words, word2vec_vectors,dep_path_word_dictionary = lstm.load_bin_vec(os.path.dirname(os.path.realpath(__file__)) +'/machine_learning_models/PubMed-w2v.bin')
            word2vec_embeddings = np.array(word2vec_vectors)
            print('finished fetching embeddings')


        return dep_type_list_dictionary, dep_path_word_dictionary, word2vec_embeddings



def build_instances_from_directory(directory_folder, entity_a, entity_b, dep_dictionary, dep_path_word_dictionary, dep_element_dictionary, between_word_dictionary,
                                   distant_interactions, reverse_distant_interactions, key_order,supplemental_dict):
    """
    build instances from directory of abstract sentences
    :param directory_folder:
    :param entity_a:
    :param entity_b:
    :param dep_dictionary:
    :param dep_path_word_dictionary:
    :param dep_element_dictionary:
    :param between_word_dictionary:
    :param distant_interactions:
    :param reverse_distant_interactions:
    :param key_order:
    :return:
    """
    total_dataset= []
    if os.path.isdir(directory_folder+'_tf_record') == False:
        os.mkdir(directory_folder+'_tf_record')
    for path, subdirs, files in os.walk(directory_folder):
        for name in files:
            if name.endswith('.txt'):
                #print(name)
                xmlpath = os.path.join(path, name)
                test_sentences, pmids = load_xml(xmlpath, entity_a, entity_b)
                candidate_instances = build_instances_testing(test_sentences, dep_dictionary, dep_path_word_dictionary, dep_element_dictionary, between_word_dictionary,
                            distant_interactions,reverse_distant_interactions, key_order, supplemental_dict)

                X = []
                y = []
                for ci in candidate_instances:
                    X.append(ci.features)
                    y.append(ci.label)
                features = np.array(X)
                labels = np.array(y)


                tfrecord_filename = name.replace('.txt','.tfrecord')

                total_dataset.append(np_to_tfrecord(features,labels,directory_folder +'_tf_record/'+ tfrecord_filename))

    return total_dataset

def build_LSTM_instances_from_directory(directory_folder, entity_a, entity_b, dep_type_list_dictionary, dep_path_word_dictionary,
                                        distant_interactions, reverse_distant_interactions, key_order,supplemental_dict):
    """
    build lstm instances from directory of abstract sentences
    :param directory_folder:
    :param entity_a:
    :param entity_b:
    :param dep_type_list_dictionary:
    :param dep_path_word_dictionary:
    :param distant_interactions:
    :param reverse_distant_interactions:
    :param key_order:
    :return:
    """
    total_dataset= []
    if os.path.isdir(directory_folder+'_lstm_tf_record') == False:
        os.mkdir(directory_folder+'_lstm_tf_record')
    for path, subdirs, files in os.walk(directory_folder):
        for name in files:
            if name.endswith('.txt'):
                #print(name)
                xmlpath = os.path.join(path, name)
                test_sentences, pmids = load_xml(xmlpath, entity_a, entity_b)
                candidate_instances = build_instances_testing(test_sentences, None, dep_path_word_dictionary, None, None,
                                                              distant_interactions, reverse_distant_interactions, key_order, supplemental_dict,dep_path_type_dictionary=dep_type_list_dictionary)

                dep_path_list_features = []
                dep_word_features = []
                dep_type_path_length = []
                dep_word_path_length = []
                labels = []
                instance_sentences = set()
                entity_a_dict = {}
                entity_b_dict = {}
                for t in candidate_instances:

                    # instance_sentences.add(' '.join(t.sentence.sentence_words))
                    dep_path_list_features.append(t.features[0:100])
                    dep_word_features.append(t.features[100:200])
                    dep_type_path_length.append(t.features[200])
                    dep_word_path_length.append(t.features[201])
                    labels.append(t.label)


                tfrecord_filename = name.replace('.txt','.tfrecord')

                total_dataset.append(np_to_lstm_tfrecord(dep_path_list_features,dep_word_features,dep_type_path_length,
                                                         dep_word_path_length,labels,directory_folder +'_lstm_tf_record/'+ tfrecord_filename))

    return total_dataset

def build_test_instances_from_directory(directory_folder, entity_a, entity_b, dep_dictionary, dep_path_word_dictionary, dep_element_dictionary, between_word_dictionary,
                                   distant_interactions, reverse_distant_interactions, key_order,supplemental_dict):
    """
    build test instances from directory of abstract folders does not make tfrecord files
    :param directory_folder:
    :param entity_a:
    :param entity_b:
    :param dep_dictionary:
    :param dep_path_word_dictionary:
    :param dep_element_dictionary:
    :param between_word_dictionary:
    :param distant_interactions:
    :param reverse_distant_interactions:
    :param key_order:
    :return:
    """

    total_features = []
    total_labels = []
    total_instances = []
    for path, subdirs, files in os.walk(directory_folder):
        for name in files:
            if name.endswith('.txt'):
                #print(name)
                xmlpath = os.path.join(path, name)
                test_sentences, pmids = load_xml(xmlpath, entity_a, entity_b)
                candidate_instances = build_instances_testing(test_sentences, dep_dictionary, dep_path_word_dictionary, dep_element_dictionary, between_word_dictionary,
                            distant_interactions,reverse_distant_interactions, key_order, supplemental_dict)

                for ci in candidate_instances:
                    total_instances.append(ci)
                    total_features.append(ci.features)
                    total_labels.append(ci.label)

    return total_instances,total_features,total_labels

def build_LSTM_test_instances_from_directory(directory_folder, entity_a, entity_b, dep_path_type_dictionary, dep_path_word_dictionary,
                                   distant_interactions, reverse_distant_interactions, key_order,supplemental_dict):
    """
    Build LSTM test instances from directory of abstract folders does not make tfrecord files
    :param directory_folder:
    :param entity_a:
    :param entity_b:
    :param dep_path_type_dictionary:
    :param dep_path_word_dictionary:
    :param distant_interactions:
    :param reverse_distant_interactions:
    :param key_order:
    :return:
    """
    total_dep_id_features = []
    total_dep_word_features = []
    total_dep_id_length = []
    total_dep_word_length = []

    total_labels = []
    total_instances = []
    for path, subdirs, files in os.walk(directory_folder):
        for name in files:
            if name.endswith('.txt'):
                #print(name)
                xmlpath = os.path.join(path, name)
                test_sentences, pmids = load_xml(xmlpath, entity_a, entity_b)
                candidate_instances = build_instances_testing(test_sentences, None, dep_path_word_dictionary, None,
                                                              None,
                                                              distant_interactions, reverse_distant_interactions,
                                                              key_order, supplemental_dict,
                                                              dep_path_type_dictionary=dep_path_type_dictionary)

                for ci in candidate_instances:
                    total_instances.append(ci)
                    total_dep_id_features.append(ci.features[0:100])
                    total_dep_word_features.append(ci.features[100:200])
                    total_dep_id_length.append(ci.features[200])
                    total_dep_word_length.append(ci.features[201])
                    total_labels.append(ci.label)

    return total_instances,total_dep_id_features,total_dep_word_features,total_dep_id_length,total_dep_word_length,total_labels

def ontology_recurse(term,path,ontology_dict):
    path.add(term)
    for t in ontology_dict[term]:
        path = ontology_recurse(t,path,ontology_dict)
    return path


def get_ontology_dictionary(filename):
    file = open(filename,'rU')
    lines = file.readlines()
    file.close()

    ontology_dict = {}
    id = ''
    for l in range(len(lines)):
        line = lines[l]
        if line.startswith('id:'):
            id = line.split()[1]
            if id not in ontology_dict:
                ontology_dict[id] = set()
        if line.startswith('is_a'):
            is_a = line.split()[1]
            ontology_dict[id].add(is_a)

    path_dict = {}
    for o in ontology_dict:
        path = set()
        path = ontology_recurse(o, path, ontology_dict)
        path_dict[o] = path

    return path_dict

def get_sentence_data_from_directory(directory_folder, entity_a, entity_b, supplemental_dict):
    """
    Build LSTM test instances from directory of abstract folders does not make tfrecord files
    :param directory_folder:
    :param entity_a:
    :param entity_b:
    :param dep_path_type_dictionary:
    :param dep_path_word_dictionary:
    :param distant_interactions:
    :param reverse_distant_interactions:
    :param key_order:
    :return:
    """

    entity_1_dict = {}
    entity_2_dict = {}
    for path, subdirs, files in os.walk(directory_folder):
        for name in files:
            if name.endswith('.txt'):
                #print(name)
                xmlpath = os.path.join(path, name)
                test_sentences, pmids = load_xml(xmlpath, entity_a, entity_b)
                for test_sentence in test_sentences:
                    entities = test_sentence.get_entities()
                    if entity_a in entities:
                        for phrase in entities[entity_a]:
                            entity_a_phrase= '_'.join([test_sentence.get_token(word).lemma for word in phrase])
                            entity_a_normalized = test_sentence.get_token(phrase[0]).get_normalized_ner()
                            e_a = entity_a_normalized + '|' + entity_a_phrase
                            if e_a not in entity_1_dict:
                                entity_1_dict[e_a] = 0
                            entity_1_dict[e_a]+=1

                        if entity_b in entities:
                            for phrase in entities[entity_b]:
                                entity_b_phrase = '_'.join([test_sentence.get_token(word).lemma for word in phrase])
                                entity_b_normalized = test_sentence.get_token(phrase[0]).get_normalized_ner()
                                e_b = entity_b_normalized + '|' + entity_b_phrase
                                if e_b not in entity_2_dict:
                                    entity_2_dict[e_b] = 0
                                entity_2_dict[e_b] += 1


    return entity_1_dict,entity_2_dict

def get_stop_list(filename):
    stop_list = set()
    if os.path.isfile(filename) is False:
        return stop_list
    with open(filename) as file:
        for line in file:
            stop_list.add(line.split()[0])
    return stop_list



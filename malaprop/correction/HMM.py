# HMM.py

from math import log10
import bisect, sys

class HMM():

    """
    This HMM is a model for spelling correction / text normalisation.

        States: a state represents the 'true' word at a given
        position.  That is, the intended word, or the normalised word
        type.  This means that the set of states is dependent on the observation.

        State transition probabilities will be the trigram
        probabilities of the state sequence.  That means we need to
        pass the backtraces.

        Emission probabilities depend on the set of variations of the
        word represented by the state, and the error rate (the
        probability that the observation is different from the 'true'
        word).
    """

    def __init__(self, confusion_set_function, trigram_model_pipe, error_rate, viterbi_type, prune_to=None, surprise_index=None, verbose=False):

        print 'prune to %d' % prune_to

        """
        error_rate and surprise_index are given in non-log form,
        trigram_model_pipe gives log forms.
        """

        self.confusion_set_function = confusion_set_function
        self.trigram_model_pipe = trigram_model_pipe
        self.error_rate = error_rate
        self.log_alpha = log10(1 - error_rate)
        if viterbi_type == 2:
            self.viterbi = self.viterbi_two
        elif viterbi_type == 3:
            self.viterbi =self.viterbi_three
        self.prune_to = prune_to
        if surprise_index is None:
            self.log_surprise_index = surprise_index
        else:
            self.log_surprise_index = log10(surprise_index)
        self.verbose = verbose

    def trigram_probability(self, three_words):

        """
        This is a little hack to use for now with BackOffTrigramModel
        and SRILM trigram models.

        The issue is that SRILM uses only one BOS and EOS marker for
        every level of language model.  The client is then expected to
        reduce the order of the query at the sentence boundaries.  For
        example, using a trigram model to estimate the probability of
        the sentence "<s> It was . </s>", we use P(It|<s>) * P(was|<s>
        It) * P(.|It was) * P(</s>|.).

        However, BackOffTrigramModel does not currently support bigram
        queries.  Until it does, we will substitute "<last_token> </s>
        </s>" with "</s> last_token </s>".  Since nothing ever appears
        after </s>, this will always give us the second bigram.
        """

        if three_words[1] == '</s>':
            bigram_inducer = ('</s>', three_words[0], three_words[1])
            return self.trigram_model_pipe.trigram_probability(bigram_inducer)
        else:
            return self.trigram_model_pipe.trigram_probability(three_words)

    def surprise_threshold_function(self, three_words):

        if three_words[1] == '</s>':
            surprise_threshold = self.trigram_model_pipe.unigram_backoff(three_words[0]) - self.log_surprise_index
        if self.trigram_model_pipe.in_bigrams(three_words[:2]):
            surprise_threshold = self.trigram_model_pipe.bigram_backoff(three_words[:2]) - self.log_surprise_index
        else:
            surprise_threshold = self.trigram_model_pipe.unigram_backoff(three_words[1]) - self.log_surprise_index
        return surprise_threshold

    def observation_emission_probability(self, var, observed):

        if var == observed:
            return self.log_alpha
        else:
            return log10(self.error_rate/len(self.confusion_set_function(var)))

    def viterbi_three(self, original_sentence):

        """
        For the trigram transitions, states have to be two words instead of one.
        """

        assert self.prune_to is not None
        if self.verbose: sys.stdout.write('.')

        assert len(original_sentence) > 0
        sentence = original_sentence + ['</s>', '</s>']

        variations = self.confusion_set_function(sentence[0])
        if self.verbose == 2: print 'variations', variations

        states = set([ ('<s>', v) for v in [sentence[0]] + variations ])
        if self.verbose == 2: print 'states', states

        path_probabilities = [{}]
        path_probability_list = [ (self.trigram_probability(('<s>',) + state) + self.observation_emission_probability(state[-1], sentence[0]), state) for state in states ]
        path_probability_list.sort()
        for (p,s) in path_probability_list[-self.prune_to:]:
            path_probabilities[0][s] = p
        if self.verbose == 2: print 'path probabilities', path_probabilities

        backtrace = { state : (state[1],) for state in states }
        if self.verbose == 2: print 'backtrace', backtrace, '\n'

        def probability_to_this_state(position, state, prior_state):

            assert prior_state[1] == state[0]
            return path_probabilities[position-1][prior_state] + \
                self.trigram_probability((prior_state[0],) + state) + \
                self.observation_emission_probability(state[1], sentence[position])


        for position in range(1, len(sentence)):
            
            if self.verbose == 2: print "Position %d" % position
            variations = self.confusion_set_function(sentence[position])
            if self.verbose == 2: print 'variations of ', sentence[position].encode('utf-8'), 
            if self.verbose == 2: print variations
            states = set([ (prior_state[-1], v) for v in [sentence[position]] + variations for prior_state in path_probabilities[position-1].keys()])
            if self.verbose == 2: print 'states', states, '\n'
            path_probabilities.append({})
            new_backtrace = {}

            path_probability_list = []
            for state in states:
                if self.verbose == 2: print 'state', state
                    
                for prior_state in path_probabilities[position-1].keys():
                    if self.verbose == 2: print 'prior state', prior_state
                    if self.verbose == 2: print 'prior state probability', path_probabilities[position-1][prior_state]


                probabilities_to_this_state = [ (probability_to_this_state(position, state, prior_state), prior_state) \
                                                   for prior_state in path_probabilities[position-1].keys() \
                                                   if prior_state[1] == state[0] ]

                if self.verbose == 2: print 'probabilities to this state', probabilities_to_this_state
                max_probability, max_prior_state = max(probabilities_to_this_state)
                bisect.insort( path_probability_list, (max_probability, state) )
                new_backtrace[state] = backtrace[max_prior_state] + (state[1],)
 
            for (p,s) in path_probability_list[-self.prune_to:]:
                path_probabilities[position][s] = p
            backtrace = new_backtrace
            if self.verbose == 2: 
                print 'backtrace', 
                for k,v in backtrace.iteritems(): print k,v
                print

        (final_probability, final_state) = max((path_probabilities[position][state], state) for state in states)
        return backtrace[final_state][:-2]

   ###################

    def viterbi_two(self, original_sentence):

        """
        Computes with trigram probabilities, but the states are only
        one word.  This corresponds to using only the first two
        trigrams for a given word.
        """
        if self.verbose: sys.stdout.write('.')

        assert len(original_sentence) > 0
        sentence = original_sentence + ['</s>', '</s>']

        first_two_words = ('<s>', '<s>')
        if self.log_surprise_index is None or self.trigram_probability(first_two_words + (sentence[0],)) < self.surprise_threshold_function(first_two_words + (sentence[0],)):
            states = set([sentence[0]] + self.confusion_set_function(sentence[0]))
        else:
            states = set([sentence[0]])
        if self.verbose == 2: print 'states', states
        path_probabilities = [ {('<s>', state): self.trigram_probability(first_two_words + (state,)) + self.observation_emission_probability(state, sentence[0]) for state in states} ]
        backtrace = {('<s>', state):('<s>', state) for state in states}
        if self.verbose == 2: print 'path probabilities', path_probabilities, '\n'

        for position in range(1, len(sentence)):

            if self.verbose == 2: print 'Position %d, word %s' % (position, sentence[position])
            
            suspicious_prior_bigrams = []
            for prior_bigram in path_probabilities[position-1].keys():
                if self.log_surprise_index is None or self.trigram_probability(prior_bigram + (sentence[position],)) < self.surprise_threshold_function(prior_bigram + (sentence[position],)):
                    suspicious_prior_bigrams.append(prior_bigram)
            if suspicious_prior_bigrams == []:
                variations = []
            else:
                variations = self.confusion_set_function(sentence[position])
            if self.verbose == 2: print 'variations', variations

            path_probabilities.append({})
            new_backtrace = {}

            # Always get the transitions to the observed word
            probabilities_to_observed = [(path_probabilities[position-1][prior_bigram] + self.trigram_probability(prior_bigram + (sentence[position],)) + self.observation_emission_probability(sentence[position], sentence[position]), prior_bigram) for prior_bigram in path_probabilities[position-1].keys()]
            if self.verbose == 2: print 'probabilities_to_observed ', probabilities_to_observed, '\n'
            max_probability, max_prior_bigram = max(probabilities_to_observed)
            path_probabilities[position][(max_prior_bigram[-1], sentence[position])] = max_probability
            new_backtrace[(max_prior_bigram[-1], sentence[position])] = backtrace[max_prior_bigram] + ( sentence[position],)

            # Get the transitions to variations
            for var in variations:
                probabilities_to_this_var = [(path_probabilities[position-1][prior_bigram] + self.trigram_probability(prior_bigram + (var,)) + self.observation_emission_probability(var, sentence[position]), prior_bigram) for prior_bigram in suspicious_prior_bigrams]
                if self.verbose == 2: print 'probabilities_to_this_var ', probabilities_to_this_var, '\n'
                max_probability, max_prior_bigram = max(probabilities_to_this_var)
                path_probabilities[position][(max_prior_bigram[-1], var)] = max_probability
                new_backtrace[(max_prior_bigram[-1],var)] = backtrace[max_prior_bigram] + (var,)
 
            backtrace = new_backtrace
            if self.verbose == 2: print 'path probabilities', path_probabilities, '\n'

        return backtrace[('</s>', '</s>')][1:-2]

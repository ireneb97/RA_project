from tqdm.auto import tqdm
import numpy as np
from collections import deque 

class Trainer(object):
    def __init__(self,agent,environment,number_of_experts,
                 automaton_encoding_size, tg_reward, num_colors = 1, goal_reward_reduction_rate = 1.0): #1 means no reduction

        assert(goal_reward_reduction_rate<=1.00)
        self.number_of_experts = number_of_experts
        self.automaton_encoding_size = automaton_encoding_size
        self.agent = agent
        self.environment = environment
        self.num_colors = num_colors
        self.goal_reward_reduction_rate = goal_reward_reduction_rate # how much of the first goals reward is given to the final one
        self.tg_reward = tg_reward
        self.reward_step = np.round(float(tg_reward)*(1/self.num_colors)*goal_reward_reduction_rate, 2)
        self.using_discount = True if (self.agent.spec['discount'] > 0 and self.agent.spec['discount'] < 1) else False

    def get_reward_from_automaton_state(self, reward, current_automaton_state, previous_automaton_state, terminal, counter_array):
        
        for i in range(1, self.num_colors+1):
            if current_automaton_state == i and previous_automaton_state == i-1:
                reward += self.reward_step
                counter_array[i-1]+=1
                if current_automaton_state == self.num_colors:
                    terminal = True
                    reward += self.reward_step*(1-self.goal_reward_reduction_rate)*(self.num_colors)
                return reward, terminal, True
        return reward, terminal, False

    def train(self,episodes = 1000):
        cum_reward = 0.0
        agent = self.agent
        environment = self.environment
        counter_arr = [0 for i in range(self.num_colors)]
        goal_collection = deque()
        goal_counter = 0

        #counter_arr_for100ep = [0 for i in range(self.num_colors)]
        #counter_arr_old = counter_arr_for100ep
        
        pbar = tqdm(range(episodes),leave = True, bar_format='{l_bar}{bar:10}{r_bar}{bar:-10b}')
        try:
            for episode in pbar:
                #if episode%1000 == 0: print("test")
                terminal = False

                #I obtain the obs and the automaton state to begin with
                states = environment.reset()

                #automaton_state = get_automaton_state_from_encoding(states['gymtpl1'], self.number_of_experts, self.automaton_encoding_size)
                automaton_state = environment._environment.environment.get_automaton_state()

                #I set the initial parameters to launch the training
                prevAutState = 0
                #Save the reward that you reach in the episode inside a linked list. This will be used for nice plots in the report.
                ep_reward = 0.0

                #agent internals
                #internals = agent.initial_internals()

                while not terminal:
                    #I start the training setting the actions
                    actions = agent.act(states=states)

                    exploration = agent.model.exploration.value().numpy()
                    if 'ppo' in self.agent.__module__:
                        lr = None
                    else:
                        lr = agent.model.optimizer.learning_rate.value().numpy()

                    #I execute(?) the environment obtaining the states, the reward and if Im in a terminal condition or not
                    states, terminal, reward = environment.execute(actions=actions)
                    
                    #Extract gym sapientino state and the state of the automaton.
                    #automaton_state = get_automaton_state_from_encoding(states['gymtpl1'], self.number_of_experts, self.automaton_encoding_size)
                    
                    automaton_state = environment._environment.environment.get_automaton_state()
                    
                    """
                        Reward shaping.
                    """
                    # if not self.using_discount and terminal == 2:
                    #     reward = -self.reward_step
                    if(not self.using_discount):reward = 0

                    reward, terminal, goal_flag = self.get_reward_from_automaton_state(reward, automaton_state, prevAutState, terminal, counter_arr)
                    
                    if terminal:

                        goal_collection.append(1) if goal_flag else goal_collection.append(0)
                    
                        if len(goal_collection) >= 100:
                            goal_collection.popleft()
                        
                        goal_counter = goal_collection.count(1)
                    
                    #I update the previous state with the state in which I was in this training cycle,regardless of the fact
                    #that I have transitated in a new relevant state.
                    prevAutState = automaton_state


                    #Update the cumulative reward during the training.
                    cum_reward += reward

                    #Update the episode reward during the training
                    ep_reward += reward
                    
                
                    pbar.set_postfix({#'reward': reward, 
                                      #'ep_reward': ep_reward, 
                                      'total_reward': cum_reward,
                                      'lr': lr,
                                      'expl':exploration, 
                                      'goal_last100ep': goal_counter,
                                      'goal': counter_arr.__str__()
                                      })

                    #let the automaton observe the reward obtained with the last action, and if he completed the task
                    agent.observe(terminal=terminal, reward=reward)
                    if terminal == True:
                        states = environment.reset()



            #Close both the agent and the environment.
            self.agent.close()
            self.environment.close()


            return dict(cumulative_reward_nodiscount = cum_reward,
                        average_reward_nodiscount = cum_reward/episodes)
        finally:

           #Let the user interrupt
           pass


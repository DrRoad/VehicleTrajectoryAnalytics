import sys                      # system tools 

import numpy as np              # numerical computing with arrays 
import pandas as pd             # dataframe as in R

import matplotlib.pyplot as plt # ploting 
import matplotlib as mpl        # ploting 
import seaborn as sns           # ploting 

from matplotlib.ticker import MultipleLocator, FormatStrFormatter

sys.path.append(r"../code")
import ccolors                  # colors from colorbrewer 

import matplotlibCharts         # own library for composite charts

import os                       # operating system io commands 
import itertools                # functonal programming tools 

import matplotlib 


class VTAnalytics:


    @classmethod
    def describe(cls, var, numerical=True, decimals=1):
        
        count = int(var.shape[0])
        na    = int(var.isnull().sum())
        
        if numerical: 
            
            var2 = var.dropna().values 
            mean = np.mean(var2)
            std  = np.std(var2)
            
            min_ =  np.min(var2)   
            pct5 =  np.percentile(var2, 5) 
            pct25 = np.percentile(var2, 25)
            pct50 = np.percentile(var2, 50)
            pct75 = np.percentile(var2, 75) 
            pct95 = np.percentile(var2, 95)

            max_ = np.max(var2)

            values = [count,   na,    mean,   std,   min_,  pct5,   pct25,  pct50,   pct75,    pct95, max_]
            values = [np.round(v, decimals) for v in values]
            #values.insert(na, 0)
            #values.insert(count, 0)
            index = ['count', 'NA', 'mean', 'std', 'min', 'ptc5', 'pct25', 'pct50', 'ptc75', 'pct95', 'max']
            
            df = pd.DataFrame({'stats':values}, index=index)
            
            return df
        else:
            raise Exception("Not implemented yet")

    @classmethod 
    def readNGISIMData(cls, fName1, start_time=None, end_time=None): 
        
        """This function takes raw NGSIM data and prepares them for analysis
        """
        
        colNames = ['VehID', 'FrameID', 'TotalFrames', 'GlobalTime', 'locX', 'locY', 'globX', 
                    'globY', 'vehLength', 'vehWidth', 'vehClass', 'vehSpeed', 'vehAcceleration', 'lane', 
                   'precedingVeh', 'followingVeh', 'spacing', 'headway']
        
        ng = pd.read_csv(fName1, 
                         header=None, names=colNames, delim_whitespace=True)
        
        #create a datetime variable 
        result = [] 
        for t in ng.GlobalTime.values: 
            t = np.datetime64(int(t),'ms') - np.timedelta64(7,'h')
            result.append(t)
        ng['_time'] = result
        
        #create a new vehicle id because the one defined in the
        #raw data is wrong 
        newVehID = (ng.groupby(['VehID', 'TotalFrames', 'vehLength'])['locY'].mean()
                            .to_frame()
                            .reset_index()
                            .reset_index())
        newVehID.rename(columns={'index':'_vid'}, inplace=True)
        newVehID.drop(['locY'], axis=1, inplace=True)
        newVehID['_vid']  = newVehID['_vid'] + 1

        ng = ng.merge(newVehID, on=['VehID', 'TotalFrames', 'vehLength'])
        
        #limit the dataset based on the input times 
        if start_time: 
            ng  = ng[(ng._time >= start_time)]
        if end_time:
            ng = ng[(ng._time <= end_time)]
        
        #calculate dt and remove records with time step greater than 
        # 0.1 seconds 

        ng = ng.sort_values(['_vid', '_time']) 
        ng['_dt'] = ng._time.shift(-1) - ng._time
        #there are some records with dt greater than the 0.1 don't know why 
        ng.loc[ng._vid != ng._vid.shift(-1), '_dt'] = np.nan

        if ng._dt.unique().shape[0] > 2:
            raise ValueError("The dataset has more than one timestep") 

        time_step = ng._dt.dropna().unique()[0]

        #recalculate the preceding and following vehicle ids 
        ng = ng.sort_values(['lane', '_time', 'locY'], ascending=[True, True, True])
        ng.index = np.arange(ng.shape[0])

        ng['_prV'] = ng._vid.shift(-1)
        ng.loc[ng.lane != ng.lane.shift(-1), '_prV'] =  np.nan 
        ng.loc[ng._time != ng._time.shift(-1), '_prV'] =  np.nan 

        ng['_flV'] = ng._vid.shift(1)
        ng.loc[ng.lane != ng.lane.shift(1), '_flV'] =  np.nan 
        ng.loc[ng._time != ng._time.shift(1), '_flV'] =  np.nan 
        
        #
        ng['_spd']  = ng.vehSpeed * 3600 / 5280  # _spd in miles per hour 
        ng['_acc']  = ng.vehAcceleration         # _acc is in feet per second squared 
        ng['_locy'] = ng.locY  #location along the Y axis in feet 
        ng['_vlen'] = ng.vehLength # vehicle length in feet  
        ng['_lane'] = ng.lane 
        

        return VTAnalytics(ng)


    @classmethod
    def readModelData(cls, fName1, start_time=None, end_time=None):

        ai = pd.read_hdf(fName1, 'trajectories')



        ai['_vid']  = np.array(ai.oid, np.int)
        ai['_time'] = ai.time
        ai['_locy'] = ai.dist_along
        ai['_lane'] = 8 - ai['laneIndex']

        if start_time:
            ai = ai[ai._time >= start_time]

        if end_time:
            ai = ai[ai._time <= end_time]

        ai = ai.sort_values(['_vid', '_time']) 
        ai['_dt'] = ai._time.shift(-1) - ai._time
        ai.loc[ai._vid != ai._vid.shift(-1), '_dt'] = np.nan

        ai = ai.sort_values(['_lane', '_time', '_locy'], ascending=[True, True, True])
        ai.index = np.arange(ai.shape[0])

        ai['_prV']        = ai._vid.shift(-1)
        ai.loc[ai._lane  != ai._lane.shift(-1), '_prV'] =  np.nan 
        ai.loc[ai._time  != ai._time.shift(-1), '_prV'] =  np.nan 

        ai['_flV'] = ai._vid.shift(1)
        ai.loc[ai._lane != ai._lane.shift(1), '_flV'] =  np.nan 
        ai.loc[ai._time != ai._time.shift(1), '_flV'] =  np.nan 

        ai['_spd'] = ai.speed
        ai['_acc'] = ai.acceleration

        return VTAnalytics(ai)


    def __init__(self, df):

        assert '_spd' in df.columns
        assert '_acc' in df.columns 

        self.df = df
        self._calculateTimeStep() 

    def __add__(self, other):

        return VTAnalytics(pd.concat([self.df, other.df]))

    def _calculateTimeStep(self):

        self.df = self.df.sort_values(['_vid', '_time']) 
        self.df['_dt'] = self.df._time.shift(-1) - self.df._time
        #there are some records with dt greater than the 0.1 don't know why 
        self.df.loc[self.df._vid != self.df._vid.shift(-1), '_dt'] = np.nan

        if self.df._dt.unique().shape[0] > 2:
            raise ValueError("The dataset has more than one timestep") 

        self.time_step = self.df._dt.dropna().unique()[0]

    def calculateAccelerationJerk(self):
        """returns a new dataset with jerk values for a time step of 1 second"""
        
        df = df.sort_values(['_vid', '_time'])

        result = [] 
        for VehId, group in df.groupby('_vid'):

            tmp2 = (group[['_time', '_acc', '_spd',  '_locy']]
                   .set_index('_time')
                   .resample('1s')
                   .mean()
                   .reset_index()
                   )

            tmp2['_vid'] = VehId

            tmp2['_jerk'] = tmp2._acc.shift(-1) - tmp2._acc
            result.append(tmp2)

        df1s = pd.concat(result)
        df1s = df1s.dropna()
        
        return df1s 


    def plotJerkDistribution(self, df, ax):
        
        
        bins = np.arange(np.floor(df._jerk.min()),
                         np.ceil(df._jerk.max()), 1)
        
        ax.hist(df._jerk, bins=bins, color='blue', 
                histtype='step', linewidth=2) 
        
        minor_locator = matplotlib.ticker.AutoMinorLocator(10)
        ax.xaxis.set_minor_locator(minor_locator)
        
        ax.set_title("Distribution of Jerk", fontsize=18)
        ax.set_xlabel("Jerk", fontsize=18)
        ax.set_ylabel("Frequency", fontsize=18)
        
        ax.grid(b=True, which='major', color='white', lw=2)
        ax.grid(b=True, which='minor', color='white', lw=0.5, alpha=1.0)
        
        return np.histogram(df._spd, bins=bins) 


    def getJerkDistribution(self, df):
        
        bins_ = np.arange(np.floor(df._jerk.min()),
                         np.ceil(df._jerk.max()), 1)
        
        hist, bins = np.histogram(df._jerk, 
                bins=bins_)

        jerk_freq = pd.DataFrame(index=bins[:-1], data=hist, columns=['freq'])
        labels = ["%.1f" % ((i+j)/2) for i,j in zip(bins[:], bins[1:])]
        jerk_freq.index = labels

        jerk_freq['Percentage'] = jerk_freq['freq'] / df.shape[0] * 100
        jerk_freq.index.name = 'bin center'
        
        return jerk_freq 


    def getARMSDistribution(self, speedbin=5):
        """Calculates ARMS for each speed bin"""
        result = [] 

        speedBins = np.array(df._spd, np.int) // speedbin * speedbin 
        for sbin, group in df.groupby(speedBins):

            arms = np.sqrt(np.sum(group._acc.dropna().values ** 2) / group.shape[0]) * 0.303

            result.append((sbin, arms, group.shape[0]))

        arms = pd.DataFrame(result, columns=['_spd', '_arms', 'n'])
        
        return arms 


    def plotARMS(self, df, ax):
    
        ax.plot(df._spd, df._arms, color='blue', lw=2)
            
        ax.set_ylabel('Acceleration Root Mean Squared', fontsize=18)
        ax.set_xlabel("Speed (mph)", fontsize=18)

    def getAccelerationDistribution(self, step):
        """Return a table of the acceleration distribution of the given time step
        """
        
        hist, bins = np.histogram(ng1s.vehAcceleration, np.arange(-21.5, 11.5, 1))
        
        acc_freq = pd.DataFrame(index=bins[:-1], data=hist, columns=['freq'])
        labels = ["%.1f <= acc < %.1f" % (i, i+1) for i in bins[:-1]]
        acc_freq.index = labels

        acc_freq['Percentage'] = acc_freq['freq'] / ng1s.shape[0] * 100

        return acc_freq 

    def plotTrajectories(self, fig, ax, lane, start_time, 
                         end_time, start_dist, end_dist, point_size=0.5):

        """
        Plot the trectories for a specific lane and time period 
        """
        
        #select the trajectories to plot based on inputs 
        tmp = self.df[self.df._lane == lane]
        tmp = tmp[tmp._time >= start_time]
        tmp = tmp[tmp._time <= end_time]
        tmp = tmp[tmp._locy >= start_dist]
        tmp = tmp[tmp._locy <= end_dist]
      
        if tmp.shape[0] == 0:
            raise ValueError("Nothing to plot")
        
        rect = 0.06,0.06,0.90,0.9
        ax = fig.add_axes(rect)
        fig.add_axes(ax)

        #define the coloring scheme for the points 
        bounds = [0, 10, 20, 30, 40, 50, 60, 70, 80]
        colors2 = ['#e31a1c','#fd8d3c', '#fecc5c','#ffffcc','#a1dab4','#41b6c4','#225ea8', '#000000']
        cmap = mpl.colors.ListedColormap(colors2) 
        norm = mpl.colors.BoundaryNorm(bounds, cmap.N)

        #define the color of the points 
        point_colors = tmp._spd.apply(lambda spd:colors2[int(spd // 10)]).values
        
        #x axis is the seconds from start time 
        times = (tmp._time - start_time).dt.total_seconds().values
        
        #y axis is the location along the corridor
        locations = tmp._locy.values 
        
        ax.scatter(times, locations, c=point_colors, s=point_size)
        ax.scatter(times[0],   locations[0], c=point_colors[0], s=point_size*8)
        ax.scatter(times[-1], locations[-1], c=point_colors[-1], s=point_size*8)
        
        
        ax.set_facecolor('white')
        ax.set_xlabel("Time in seconds from %s" % str(start_time), fontsize=18)
        ax.set_ylabel("Distance from Starting point %.1f (feet)" % start_dist,
                      fontsize=18)
        
        ax.set_xlim([times.min(), times.max()])
        ax.set_ylim([locations.min(), locations.max()])
        
        cmax = fig.add_axes([0.96, 0.1, 0.02, 0.8])
        mpl.colorbar.ColorbarBase(ax=cmax, cmap=cmap, norm=norm, boundaries=bounds) 

        ax.set_axisbelow(True)
        ax.grid(color='grey', lw=1, linestyle='dashed', alpha=0.2)
    
    def calculateSpaceMeanSpeedAndDensity(self, time_bin, space_bin):
        
        """time_bin in seconds 
        space_bin in feet """

        df['_spacebin'] = np.array(df._locy // space_bin, np.int)
        df['_timebin'] = pd.to_datetime(((ng._time.astype(np.int64) // 
                                         (time_bin * 1e9) ) * (time_bin * 1e9) ))
        
        df_hm = (df.groupby(['_lane', '_spacebin', '_timebin'])['_spd']
                          .aggregate([np.mean, np.size]))

        df_hm = (df_hm.reset_index()
                      .rename(columns={'size':'density', 'mean':'speed', '_lane':'_lane'}) ) 

        mi = pd.MultiIndex.from_product([sorted(df._lane.unique()), 
                                         sorted(df._spacebin.unique()), 
                                         df._timebin.unique()], 
                                         names=['_lane', '_spacebin', '_timebin'])
        mi = pd.DataFrame(index=mi)
        mi.reset_index(inplace=True)

        df_hm = df_hm.merge(mi, on=['_lane', '_spacebin', '_timebin'], how='right')
        df_hm = df_hm.set_index(['_lane', '_spacebin', '_timebin'])


        ### the simulation time step is 0.1 seconds this is why I am multiplying by 10 below 
        ##TODO change the 10 
        df_hm['density'] = df_hm['density'] * (5280 / space_bin) / (time_bin * 10)
        
        return df_hm 

    def plotMeanCorridorSpeedDistribtution(self,df, ax):
        """
        '_vid', 'start', 'startDist', 'end', 'endDist', 'dur', 'dist', 'speed'], dtype='object'
        """
        
        bins = np.arange(np.floor(df._spd.min()),
                         np.ceil(df._spd.max()), 1)
        
        ax.hist(df._spd, bins=bins, color='blue', histtype='step', linewidth=2) 
        
        minor_locator = matplotlib.ticker.AutoMinorLocator(10)
        ax.xaxis.set_minor_locator(minor_locator)
        
        ax.set_title("Distribution of Average Vehicle Speed", fontsize=18)
        ax.set_xlabel("Speed(mph)", fontsize=18)
        ax.set_ylabel("Frequency", fontsize=18)
        
        ax.grid(b=True, which='major', color='white', lw=2)
        ax.grid(b=True, which='minor', color='white', lw=0.5, alpha=1.0)
        
        return np.histogram(df._spd, bins=bins)

    def calculateCorridorTravelTimes(self):
        
        df = df.sort_values(['_vid', '_time'])
        tmp1 = (df.groupby('_vid')[['_time', '_locy']]
                .first().reset_index()
                .rename(columns={'_time':'start', '_locy':'startDist'}))
        
        tmp2 = (df.groupby('_vid')[['_time', '_locy']]
                .last().reset_index()
                .rename(columns={'_time':'end', '_locy':'endDist'}))
        
        cor_times = pd.merge(tmp1, tmp2, on=['_vid'])
        
        cor_times['dur'] = (cor_times.end - cor_times.start).dt.total_seconds() 
        cor_times['dist'] = cor_times.endDist - cor_times.startDist 
        cor_times['_spd'] = (cor_times.dist / 5280.0) / (cor_times.dur / 3600.0)
        
        return cor_times 

    def getSpeedDistribution(self, ax):
        
        bins = np.arange(np.floor(df._spd.min()), np.ceil(df._spd.max()), 1)
        
        ax.hist(df._spd, bins=bins, color='blue', histtype='step', linewidth=2) 
        
        minor_locator = matplotlib.ticker.AutoMinorLocator(10)
        ax.xaxis.set_minor_locator(minor_locator)
        
        ax.set_title("Distribution of Speed", fontsize=18)
        ax.set_xlabel("Speed(mph)", fontsize=18)
        ax.set_ylabel("Frequency", fontsize=18)
        
        ax.grid(b=True, which='major', color='white', lw=2)
        ax.grid(b=True, which='minor', color='white', lw=0.5, alpha=1.0)
        
        return np.histogram(df._spd, bins=bins)

    def getAccelerationDistribution(self):
        
        bins = np.arange(np.floor(df._acc.min()) - 0.5, np.ceil(df._acc.max()) + 0.5, 1)
        
        ax.hist(df._acc, bins=bins, color='blue', histtype='step', linewidth=2) 
        
        ax.set_title("Distribution of Acceleration", fontsize=18)
        ax.set_xlabel("Acceleration(fpss)", fontsize=18)
        ax.set_ylabel("Frequency", fontsize=18)
        
        minor_locator = matplotlib.ticker.AutoMinorLocator(5)
        ax.xaxis.set_minor_locator(minor_locator)
        
        ax.grid(b=True, which='major', color='white', lw=2)
        ax.grid(b=True, which='minor', color='white', lw=0.5, alpha=1.0)
    
    def getFundamentalMacroscopicVars(self, space_bin, time_bin):

        """time_bin in seconds 
        space_bin in feet """

        self.df['_spacebin'] = np.array(self.df._locy // space_bin, np.int)
        self.df['_timebin'] = pd.to_datetime(((self.df._time.astype(np.int64) // 
                                         (time_bin * 1e9) ) * (time_bin * 1e9) ))
        
        df_hm = (self.df.groupby(['_lane', '_spacebin', '_timebin'])['_spd']
                          .aggregate([np.mean, np.size]))

        df_hm = (df_hm.reset_index()
                      .rename(columns={'size':'density', 'mean':'speed', '_lane':'_lane'}) ) 

        mi = pd.MultiIndex.from_product([sorted(self.df._lane.unique()), 
                                         sorted(self.df._spacebin.unique()), 
                                         self.df._timebin.unique()], 
                                         names=['_lane', '_spacebin', '_timebin'])
        mi = pd.DataFrame(index=mi)
        mi.reset_index(inplace=True)
        #
        #
        df_hm = df_hm.merge(mi, on=['_lane', '_spacebin', '_timebin'], how='right')
        df_hm = df_hm.set_index(['_lane', '_spacebin', '_timebin'])


        ### the simulation time step is 0.1 seconds this is why I am multiplying by 10 below 
        ##TODO change the 10 
        time_step_in_sec = self.time_step.astype(np.int64) / 1e9

        df_hm['density'] = df_hm['density'] * (5280 / space_bin) / (time_bin / time_step_in_sec)
        

        return df_hm 

    def plotVehicleTrajectories(self, fig, ax, veh_ids):
    
        #define the coloring scheme for the points 
        bounds = [0, 10, 20, 30, 40, 50, 60, 70, 80]
        colors2 = ['#e31a1c','#fd8d3c', '#fecc5c','#ffffcc','#a1dab4','#41b6c4','#225ea8', '#000000']
        cmap = mpl.colors.ListedColormap(colors2) 
        norm = mpl.colors.BoundaryNorm(bounds, cmap.N)
        
        for veh_id in veh_ids:
            
            tmp = df[df._vid == veh_id]
            
            locations = tmp._locy.values 
            times = (tmp._time - start_time).dt.total_seconds().values
            
            #define the color of the points 
            point_colors = tmp._spd.apply(lambda spd:colors2[int(spd // 10)]).values
            
            #y axis is the location along the corridor
            locations = tmp._locy.values 
            
            ax.scatter(times, locations, c=point_colors, s=1)



    def plotSpeedVsDensity(self)

        ai_hm_mean = (ai_hm.groupby(ai_hm.density.values // 5 * 5)['speed'].aggregate([np.mean, np.size])
                      .reset_index()
                      .rename(columns={'index':'density', 'mean':'mean_speed'}))


        fig, ax1 = plt.subplots(figsize=(15,10))

        grey_points = ax1.scatter(ai_hm.density, ai_hm.speed, s=1, color='blue', label=None)

        ax1.set_xlim([0,250])
        tmp = ai_hm_mean[ai_hm_mean['size'] > 100]
        mean_line = ax1.plot(tmp.density, tmp.mean_speed, c='blue', label="mean Model speed")
        ax1.legend(fontsize=16)

        ax1.legend(fontsize=16)

        ax1.set_ylabel("Speed (mph)", fontsize=18)
        ax1.set_xlabel('Density (vpm)', fontsize=18)

        fig.text(0.85, 0.65, "SpaceBin:%dft\nTimeBin:%dsec" % (LCR_SPACE_BIN, LCR_TIME_BIN), fontsize=18)

        fig.tight_layout()

    def plotSpeedVsDensityByLane(self):

        fig = plt.figure(figsize=(15, 15), dpi=150)

        gs = mpl.gridspec.GridSpec(4, 2)

        for laneNum in range(1, 8):
            
            i = (laneNum - 1) // 2
            j = (laneNum - 1) % 2 
            
            ax = plt.subplot(gs[i,j])
            
            tmp = ai_hm.loc[laneNum]
            
            
            ax.scatter(tmp.density, tmp.speed, s=1.5, color='blue', label=None)
            ax.set_xlim([0,250])
            ax.set_ylim([0,65])
            ax.set_title("Lane %d" % laneNum, fontsize=14)
            
            tmp_mean = (tmp.groupby(tmp.density.values // 5 * 5)['speed']
                              .aggregate([np.mean, np.size])
                              .reset_index()
                              .rename(columns={'index':'density', 'mean':'mean_spd'}))
            
            tmp_mean = tmp_mean[tmp_mean['size'] > 50]
            
            ax.plot(tmp_mean.density, tmp_mean.mean_spd, c='blue', label='mean model speed')
            
            if j == 1:
                ax.set_yticklabels([])
                
            if j == 0:
                ax.set_ylabel("Speed (mph)", fontsize=18)
                
            ax.legend(fontsize=18)

        plt.subplot(gs[3,0]).set_xlabel("Density (vpm)", fontsize=18)
        plt.subplot(gs[2,1]).set_xlabel("Density (vpm)", fontsize=18)

        fig.tight_layout()
        fig.text(0.72, 0.13, "SpaceBin:%dft\nTimeBin:%dsec" % (LCR_SPACE_BIN, LCR_TIME_BIN), fontsize=18)
        #fig.savefig(os.path.join(OUT_FOLDER, "  density vs speed per lane.png"), dpi=150)


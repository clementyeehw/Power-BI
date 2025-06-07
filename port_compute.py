import numpy as np
import pandas as pd
pd.options.mode.chained_assignment = None
from scipy.stats import norm

class portmetrics():

    def __init__(self, returns=np.array([]), risks=np.array([]), correlations=np.array([]), weights=np.array([]),
                 risk_free=0, periods=[1, 5, 10], significance=0.05):
        # Note #1: Input arrays / matrix for returns, risks and correlations must adopt the same asset order.
        # Note #2: weights matrix must include a PortfolioId column and must follow the same asset order as Note #1. 
        # Note #3: Functions that end with matrix in their names perform underlying calcs on all given portfolios.
        self.returns, self.risks, self.correlations = self.vectorize(returns, risks, correlations)
        self.portfolio_ids = np.array(weights["PortfolioId"])
        self.weights = self.transpose_weights(weights)
        self.risk_free = risk_free # Government cash by default
        self.periods = periods # Measured in years
        self.significance = significance # 5% significance level by default
    
    def get_lognorm_port_matrix(self):
        log_rets = np.log(self.returns + 1) # Assume CMA asset returns follow a lognormal distrubtion
        variances = np.log(np.sqrt(pow(self.risks, 2) / np.exp(log_rets * 2) + 0.25) + 0.5) # CMA asset variances
        mean_lognorm_rets = np.exp(log_rets + variances/2) - 1
        port_mean_lognorm_rets = np.dot(mean_lognorm_rets, self.weights) 
        port_lognorm_vol = self.get_lognorm_risk_matrix()
        port_normal_var = np.log(1 + np.square(port_lognorm_vol / (1 + port_mean_lognorm_rets)))
        port_normal_rets = np.log(1 + port_mean_lognorm_rets) - 0.5 * port_normal_var
        port_median_lognorm_rets = np.exp(port_normal_rets) - 1
        port_sharpes = (port_median_lognorm_rets - self.risk_free) / port_lognorm_vol
        port_VaRs = [np.exp(port_normal_rets + norm.ppf(self.significance)* np.sqrt(port_normal_var / period)) - 1 
                     for period in self.periods] 
        port_upsides = [np.exp(port_normal_rets + norm.ppf(1 - self.significance)* np.sqrt(port_normal_var / period)) - 1
                        for period in self.periods]
        # Create metrics DataFrame
        metrics = np.vstack((self.portfolio_ids, port_median_lognorm_rets, port_lognorm_vol, port_sharpes))
        for arr in [port_VaRs, port_upsides]:
            for idx in range(len(self.periods)):
                metrics = np.vstack((metrics, arr[idx]))
        df = pd.DataFrame(data=metrics.T,
                          columns=["PortfolioId", "PortfolioMedianLogNormReturn", "PortfolioLogNormVol", "PortfolioSharpe"] + 
                          [f"{int(self.significance * 100)}%_VaR_{period}Y" for period in self.periods] + 
                          [f"{int(self.significance * 100)}%_Upside_{period}Y" for period in self.periods])
        df["PortfolioId"] = df["PortfolioId"].astype(int)
        return df

    def get_lognorm_risk_matrix(self):
        return np.diag(np.sqrt(np.matmul(np.matmul(self.weights.T, self.compute_cov_matrix()), self.weights).clip(min=0)))

    def compute_cov_matrix(self):
        return np.dot(np.dot(np.diag(self.risks), self.correlations), np.diag(self.risks))

    def get_weighted_ret_matrix(self):
        return np.dot(self.returns, self.weights)

    def transpose_weights(self, weights):
        if len(weights)==0:
            raise Exception("Weights matrix is empty. Please reinitialize the class before calling any built-in class functions!")
        else:
            w_ = weights.set_index("PortfolioId")
            w_.index.name = None
            return w_.T.to_numpy()

    def vectorize(self, *args):
        params = ["returns", "risks", "correlations"]
        lst = []
        sizes = []
        for idx, arg in enumerate(args):
            v = np.array(arg)
            if v.size == 0:
                print(f"{params[idx]} is empty array. Please reinitialize the class before calling any built-in class functions!")
            else:
                lst.append(v)
                sizes.append(len(v))
        if len(sizes) == 0:
            raise Exception("Empty arrays detected. See error message above for more details!")
        elif len(sizes) != 0 and np.average(sizes) != sizes[0]:
            raise Exception("returns, risks and correlations must have the same dimensions. Please reinitialize the class!")
        else: 
            return lst if len(lst) > 1 else lst[0] if len(lst) == 1 else None 
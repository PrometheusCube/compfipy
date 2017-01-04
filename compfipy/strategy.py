"""
strategy.py

Defines a class that contains a strategy definition and the functions to trade on that strategy.
The Strategy operates on a portfolio.

"""

import tabulate
import numpy as np
import pandas as pd

# General Strategy Class
# ------------------------------------------------------------------------------------------------------------------------------
# pylint: disable=too-many-instance-attributes,too-many-arguments
class Strategy(object):
    """
    Defines a particular trade strategy
    """

    def __init__(
            self,
            portfolio,
            market,
            commission_min=1.00,
            commission=0.0075,
            buy_percent=1.0,
            sell_percent=1.0,
            pm_threshold=0.0,
            pm_order=1.0,
            risk_free_return=1.0
        ):
        """
        Create base Strategy object.
        """

        # Assumptions
        self.quiet = False
        self.commission_min = commission_min
        self.commission = commission
        self.buy_percent = buy_percent
        self.sell_percent = sell_percent
        self.pm_threshold = pm_threshold
        self.pm_order = pm_order
        self.risk_free_return = risk_free_return

        # Inputs
        self.portfolio = portfolio
        self.market = market

        # Trading states
        self.long_open = {symbol:False for symbol in portfolio.assets.keys()}
        self.short_open = {symbol:False for symbol in portfolio.assets.keys()}

        # Keep track of intermidiate results for performance
        self.display_data = []
        recordings = [
            'buy price', 'buy shares', 'buy fees', 'buy date',
            'sell price', 'sell shares', 'sell fees', 'sell date',
            'gain', 'profit', 'loss', 'return', 'win/loose',
            'min balance', 'min date', 'max balance', 'max date',
            'drawdown', 'drawdown days',
            'volatility', 'expected_return', 'beta', 'lpm', 'hpm',
            'max', 'mean', 'min'
        ]
        self.record = {symbol:pd.DataFrame(columns=recordings) for symbol in portfolio.assets.keys()}
        self.max = {symbol:[portfolio.assets[symbol].c.iloc[0], None] for symbol in portfolio.assets.keys()}
        self.min = {symbol:[999999999999999, None] for symbol in portfolio.assets.keys()}
        self.drawdown = {symbol:[999999999999999, None] for symbol in portfolio.assets.keys()}

    def calc_fee(self, shares):
        """
        Calculate the total fees for a given trade of shares.
        """
        return max(self.commission_min, abs(self.commission * shares))

    def on_date(self, date):
        """
        Called for each date of portfolio data, implements trading logic.
        """
        pass

    def enter_long(self, symbol, date, shares):
        """
        Enter a long position.
        """
        # Set trategy state
        self.long_open[symbol] = True
        # Apply trade to portfolio
        self.portfolio.trade(symbol, date, shares, self.commission_min, self.commission)

        # Set min, max & drawdown
        self.max[symbol] = [self.portfolio.assets[symbol].c[date], date]
        self.min[symbol] = [self.portfolio.assets[symbol].c[date], date]
        self.drawdown[symbol] = [self.portfolio.assets[symbol].c[date], date]

        # Create a record of the trade
        record = {
            'buy price' : [self.portfolio.assets[symbol].c[date]],
            'buy shares' : [shares],
            'buy fees' : [self.calc_fee(shares)],
            'buy date' : [date],
            'sell price' : [None],
            'sell shares' : [None],
            'sell fees' : [None],
            'sell date' : [None],
            'gain' : [None],
            'profit' : [None],
            'loss' : [None],
            'return' : [None],
            'win/loose' : [None],
            'min balance':[None],
            'max balance':[None],
            'min date':[None],
            'max date':[None],
            'drawdown':[None],
            'drawdown days':[None],
            'volatility':[None],
            'expected_return':[None],
            'beta':[None],
            'lpm':[None],
            'hpm':[None],
            'max':[None],
            'mean':[None],
            'min':[None]
        }

        # Log this trades record
        self.record[symbol] = self.record[symbol].append(pd.DataFrame(record), ignore_index=True)

        return self

    def exit_long(self, symbol, date, shares):
        """
        Exit a long position.
        """
        # Set trategy state
        self.long_open[symbol] = False
        # Apply trade to portfolio
        self.portfolio.trade(symbol, date, -1.0 * shares, self.commission_min, self.commission)
        # Get the last record (should be the trade that entered long)
        i = self.record[symbol].index[-1]

        # Update Sell info for this trade record
        self.record[symbol].loc[i, 'sell price'] = self.portfolio.assets[symbol].c[date]
        self.record[symbol].loc[i, 'sell shares'] = shares
        self.record[symbol].loc[i, 'sell fees'] = self.calc_fee(shares)
        self.record[symbol].loc[i, 'sell date'] = date

        # Get trade data from the record and calculate gain
        initial = self.record[symbol].loc[i, 'buy price'] * self.record[symbol].loc[i, 'buy shares']
        final = self.record[symbol].loc[i, 'sell price'] * self.record[symbol].loc[i, 'sell shares']
        fees = self.record[symbol].loc[i, 'sell fees'] + self.record[symbol].loc[i, 'sell fees']
        gain = (final - initial)

        # Update Performance info for this trade record
        self.record[symbol].loc[i, 'gain'] = gain
        self.record[symbol].loc[i, 'return'] = gain / initial

        self.record[symbol].loc[i, 'profit'] = gain if gain > 0 else 0
        self.record[symbol].loc[i, 'loss'] = (abs(gain) + fees) if gain < 0 else fees

        # Update Trade info for this trade record
        if gain > 0:
            self.record[symbol].loc[i, 'win/loose'] = 'w'
        elif gain < 0:
            self.record[symbol].loc[i, 'win/loose'] = 'l'
        else:
            self.record[symbol].loc[i, 'win/loose'] = '-'

        self.record[symbol].loc[i, 'min balance'] = self.min[symbol][0] * self.record[symbol].loc[i, 'buy shares']
        self.record[symbol].loc[i, 'max balance'] = self.max[symbol][0] * self.record[symbol].loc[i, 'buy shares']

        self.record[symbol].loc[i, 'min date'] = self.min[symbol][1]
        self.record[symbol].loc[i, 'max date'] = self.max[symbol][1]

        drawdown_price = (self.max[symbol][0] - self.drawdown[symbol][0])
        self.record[symbol].loc[i, 'drawdown'] = drawdown_price * self.record[symbol].loc[i, 'buy shares']
        self.record[symbol].loc[i, 'drawdown days'] = (self.drawdown[symbol][1] - self.max[symbol][1]).days

        # Get asset and market prices for the time period of this trade
        time_range = pd.date_range(self.record[symbol].loc[i, 'buy date'], self.record[symbol].loc[i, 'sell date'])
        trade_prices = self.portfolio.assets[symbol].c[time_range]
        market_prices = self.market.c[time_range]

        # Calculate trade vs market return then calculate Beta
        returns = trade_prices.pct_change()
        market_returns = market_prices.pct_change()
        asset_and_market = pd.DataFrame({'asset': returns, 'market': market_returns})
        beta = asset_and_market.cov()['asset']['market'] / market_returns.std()

        # Update the risk info and market comparison for this trade record
        self.record[symbol].loc[i, 'volatility'] = returns.std()
        self.record[symbol].loc[i, 'expected_return'] = returns.mean()
        self.record[symbol].loc[i, 'beta'] = beta

        # Update the  info for this trade record
        self.record[symbol].loc[i, 'hpm'] = ((returns - self.pm_threshold).clip(0) ** self.pm_order).sum() / len(returns)
        self.record[symbol].loc[i, 'lpm'] = ((self.pm_threshold - returns).clip(0) ** self.pm_order).sum() / len(returns)

        # Update the Price info for this trade record
        self.record[symbol].loc[i, 'max'] = trade_prices.max()
        self.record[symbol].loc[i, 'mean'] = trade_prices.mean()
        self.record[symbol].loc[i, 'min'] = trade_prices.min()

        return self

    def enter_short(self, symbol): #, date, shares
        """
        Enter a short position.
        """
        self.short_open[symbol] = True

    def exit_short(self, symbol): #, date, shares
        """
        Exit a short position.
        """
        self.short_open[symbol] = False

    def run(self):
        """
        Iterates over data.
        """
        self.before_run()
        for date in self.portfolio.cash.index:
            self.on_date(date)
        self.after_run()

    def before_run(self):
        """
        Called at the start of run.
        """
        self.display_data = []
        return self

    def after_run(self):
        """
        Called at the end of run.
        """
        if not self.quiet:
            print tabulate.tabulate(self.display_data, headers=['trade', 'symbol', 'date', 'price', 'shares', 'value', 'cash'])
            print
            # Calculate the performance of the strategy
            performance = self.calc_performance()
            # Make a list of headers
            assets = [' '] + performance.keys()
            # Package the performance dict into a list of lists for the tabulate function
            perf = [performance.values()[0].keys()] \
                 + [[p for p in asset_performance.values()]
                    for asset_performance in performance.values()
                   ]
            perf = [list(x) for x in zip(*perf)]
            # Dsiplay a table of the performance
            print tabulate.tabulate(perf, headers=assets, floatfmt=".2f")

    def calc_performance(self):
        """
        Calculate performance of strategy.
        """
        performance = {}
        for symbol in self.portfolio.assets.keys():

            # Total the Performance of all the trades
            trades = len(self.record[symbol])
            profit = self.record[symbol]['profit'].sum()
            loss = self.record[symbol]['loss'].sum()
            # Total or average the trade info for all the trades
            try:
                wins = len(self.record[symbol].groupby('win/loose').groups['w'])
            except ValueError:
                wins = 0
            try:
                losses = len(self.record[symbol].groupby('win/loose').groups['l'])
            except ValueError:
                losses = 0
            try:
                washes = len(self.record[symbol].groupby('win/loose').groups['-'])
            except ValueError:
                washes = 0
            max_drawdown = self.record[symbol]['drawdown'].max()
            average_drawdown = self.record[symbol]['drawdown'].mean()
            max_drawdown_time = self.record[symbol]['drawdown days'].max()
            average_drawdown_time = self.record[symbol]['drawdown days'].mean()
            # Average the risk and market comparisons for all trades
            vol_risk = self.record[symbol]['volatility'].mean()
            beta = self.record[symbol]['beta'].mean()
            lpm_risk = self.record[symbol]['lpm'].mean()
            e_r = self.record[symbol]['expected_return'].mean()
            # Calculate Risk measures
            treynor_ratio = (e_r - self.risk_free_return) / beta
            sharpe_ratio = (e_r - self.risk_free_return) / vol_risk
            # Package up the data for each symbol
            performance[symbol] = {
                'trades': trades,
                'wins': wins,
                'losses': losses,
                'washes': washes,
                'profit': profit,
                'loss': loss,
                'net_profit': profit - loss,
                'profit_factor': profit / loss,
                'percent_profitable': wins / trades,
                'average_trade_net_profit' : (profit - loss) / trades,
                'max_drawdown' : max_drawdown,
                'average_drawdown' : average_drawdown,
                'max_drawdown_days' : max_drawdown_time,
                'average_drawdown_days' : average_drawdown_time,
                'volatility_risk' : vol_risk,
                'beta' : beta,
                'lower_partial_moment_risk' : lpm_risk,
                't_r' : treynor_ratio,
                's_r' : sharpe_ratio
            }

        return performance

# Specific Strategy Class
# ------------------------------------------------------------------------------------------------------------------------------
class SimpleMovingAverageCrossover(Strategy):
    """
    Buy when sma(fast) crosses above sma(slow), sell when sma(fast) crosses below sma(slow)
    """
    def __init__(self, portfolio, market, fast, slow):
        Strategy.__init__(self, portfolio, market)
        self.fast = fast
        self.slow = slow

    def on_date(self, date):
        """
        Iterates over dates.
        """

        for symbol in self.portfolio.assets.keys():

            # Don't do anything until there are enough days to compare to the slower moving average
            if len(self.portfolio.assets[symbol].c[:date]) > self.slow:

                # Get today's price
                price = self.portfolio.assets[symbol].c[date]

                # Record min, max & drawdown
                if price > self.max[symbol][0]:
                    self.max[symbol] = [price, date]
                    # reset drawdown
                    self.drawdown[symbol] = [price, date]

                if price < self.min[symbol][0]:
                    self.min[symbol] = [price, date]

                if price < self.drawdown[symbol][0]:
                    self.drawdown[symbol] = [price, date]

                # Calculate moving averages
                sma_fast = np.ma.average(self.portfolio.assets[symbol].c[:date], self.fast).iloc[-2:]
                sma_slow = np.ma.average(self.portfolio.assets[symbol].c[:date], self.slow).iloc[-2:]

                # Determine crossover and direction
                xover = np.sign(np.sign(sma_fast - sma_slow).diff()).iloc[-1]

                # If the crossover goes positive and we are not already long
                if xover > 0 and not self.long_open[symbol]:
                    # Determine shares to trade, make the trade, and display message
                    shares = (self.buy_percent * self.portfolio.cash[date]) / price
                    self.enter_long(symbol, date, shares)
                    self.display_data.append(
                        ['buy', symbol, str(date.date()), price, shares, price * shares, self.portfolio.cash[date]]
                    )

                # If the crossover goes negative and we have a long position open or we've reached the end of our data and we
                # are still in a long position
                elif (xover < 0 and self.long_open[symbol]) or (date == self.portfolio.cash.index[-1] and self.long_open[symbol]):
                    # Determine shares to trade, make the trade, and display message
                    shares = self.sell_percent * self.portfolio.positions[symbol][date]
                    self.exit_long(symbol, date, shares)
                    self.display_data.append(
                        ['sell', symbol, str(date.date()), price, shares, price * shares, self.portfolio.cash[date]]
                    )

class BuyAndHold(Strategy):
    """
    Buy on the first day, *never* sell (ok, sell on the last day just to calculate stuff, lol).
    """

    def on_date(self, date):
        """
        Iterates over dates.
        """

        for symbol in self.portfolio.assets.keys():

            # Get today's price
            price = self.portfolio.assets[symbol].c[date]

            # If the first day
            if date == self.portfolio.assets[symbol].c.index[0]:

                # Determine the number of shares to buy based on the current price and the available cash
                shares = (self.buy_percent * self.portfolio.cash[date]) / price
                # Make the trade
                self.enter_long(symbol, date, shares)

                # Print some data to the console
                self.display_data.append(
                    ['buy', symbol, str(date.date()), price, shares, price * shares, self.portfolio.cash[date]]
                )

            # If the last day
            elif date == self.portfolio.assets[symbol].c.index[-1]:


                # Determine the number of shares to sell based on the current position and the sell percent
                shares = self.sell_percent * self.portfolio.positions[symbol][date]
                # Make the trade
                self.exit_long(symbol, date, shares)

                # Print some data to the console
                self.display_data.append(
                    ['sell', symbol, str(date.date()), price, shares, price * shares, self.portfolio.cash[date]]
                )

        return self

# -*- coding: utf-8 -*-
import warnings

import numpy as np
import torch


class BFGS():
    def __init__(self, atoms, maxstep=0.04, fmax=0.05, alpha=70):
        """BFGS optimizer.

        Parameters:

        atoms: Atoms object
            The Atoms object to relax.

        maxstep: float
            Used to set the maximum distance an atom can move per
            iteration (default value is 0.04 Å).

        """
        if maxstep > 1.0:
            warnings.warn('You are using a much too large value for '
                          'the maximum step size: %.1f Å' % maxstep)
        self.maxstep = maxstep
        self.atoms = atoms
        self.H = None
        self.H0 = torch.eye(3 * len(self.atoms), dtype=torch.float64) * alpha
        self.r0 = None
        self.f0 = None
        self.fmax = fmax
        self.nsteps = 0
        # maximum number of steps placeholder with maxint
        self.max_steps = 100000000

    def converged(self):
        forces = self.atoms.get_forces()
        return (forces ** 2).sum(axis=1).max() < self.fmax ** 2

    def run(self, fmax=0.05):
        with torch.no_grad():
            while not self.converged() and self.nsteps < self.max_steps:

                self.step()
                self.nsteps += 1

                forces = self.atoms.get_forces()
                print(self.nsteps, np.sqrt((forces ** 2).sum(axis=1).max()))


    def get_forces(self):
        return self.atoms.get_forces()

    def get_positions(self):
        return self.atoms.get_positions()

    def set_positions(self, update):
        r = self.get_positions()
        self.atoms.set_positions(r + update)

    def step(self):
        r = self.get_positions()
        f = self.get_forces()
        f = f.reshape(-1)

        arg1 = torch.from_numpy(r.flatten()) #r has to be converted to torch tensor
        arg2 = torch.from_numpy(f)           #f has to be converted to torch tensor

        self.update(arg1, arg2, self.r0, self.f0)
        
        omega1, V1 = torch.symeig(self.H, eigenvectors=True)
        dr1 = torch.matmul(V1, torch.matmul(arg2, V1)/torch.abs(omega1))
        dr1 = dr1.view(-1, 3)
        steplengths1 = (dr1**2).sum(1)**0.5
        dr1 = self.determine_step(dr1, steplengths1)

        self.set_positions(dr1.numpy())

        self.r0 = arg1.clone() 
        self.f0 = arg2.clone()

    def determine_step(self, dr, steplengths):
        """Determine step to take according to maxstep

        Normalize all steps as the largest step. This way
        we still move along the eigendirection.
        """
        maxsteplength = torch.max(steplengths)
        if maxsteplength >= self.maxstep:
            dr *= self.maxstep / maxsteplength

        return dr

    def update(self, r, f, r0, f0):
        if self.H is None:
            self.H = self.H0
            return
        dr = r - r0

        if torch.abs(dr).max() < 1e-7:
            # Same configuration again (maybe a restart):
            return

        df = f - f0
        a = torch.dot(dr, df) 
        dg = torch.matmul(self.H , dr)
        b = torch.dot(dr, dg)
        val = torch.ger(df, df) / a + torch.ger(dg, dg) / b
        self.H -= val

